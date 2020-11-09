# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from abc import ABC, abstractmethod
import asyncio
import logging

from mautrix.appservice import AppService, IntentAPI
from mautrix.types import (RoomID, EventID, MessageEventContent, EventType, EncryptionAlgorithm,
                           RoomEncryptionStateEventContent as Encryption, UserID)
from mautrix.errors import MatrixError, MatrixRequestError, MatrixConnectionError
from mautrix.util.logging import TraceLogger
from mautrix.util.simple_lock import SimpleLock

if TYPE_CHECKING:
    from .user import BaseUser
    from .matrix import BaseMatrixHandler
    from .bridge import Bridge


class BasePortal(ABC):
    log: TraceLogger = logging.getLogger("mau.portal")
    bad_gateway_sleep: int = 5
    az: AppService
    matrix: 'BaseMatrixHandler'
    bridge: 'Bridge'
    loop: asyncio.AbstractEventLoop
    main_intent: IntentAPI
    mxid: Optional[RoomID]
    name: Optional[str]
    encrypted: bool
    backfill_lock: SimpleLock

    @abstractmethod
    async def save(self) -> None:
        pass

    @abstractmethod
    async def handle_matrix_message(self, sender: 'BaseUser', message: MessageEventContent,
                                    event_id: EventID) -> None:
        pass

    async def enable_dm_encryption(self) -> bool:
        try:
            await self.main_intent.invite_user(self.mxid, self.az.bot_mxid)
            await self.az.intent.join_room_by_id(self.mxid)
            await self.main_intent.send_state_event(self.mxid, EventType.ROOM_ENCRYPTION,
                                                    Encryption(EncryptionAlgorithm.MEGOLM_V1))
        except Exception:
            self.log.warning(f"Failed to enable end-to-bridge encryption", exc_info=True)
            return False

        self.encrypted = True
        return True

    async def _send_message(self, intent: IntentAPI, content: MessageEventContent,
                            event_type: EventType = EventType.ROOM_MESSAGE, retries: int = 4,
                            **kwargs) -> EventID:
        while True:
            try:
                return await self._send_message_direct(intent, content, event_type, **kwargs)
            except MatrixRequestError as e:
                if not retries or e.http_status not in (502, 504):
                    raise
                self.log.warning("Got gateway error trying to send message, retrying in "
                                 f"{self.bad_gateway_sleep} seconds")
            except MatrixConnectionError as e:
                if not retries:
                    raise
                self.log.warning(f"Got connection error trying to send message: {e}, retrying in "
                                 f"{self.bad_gateway_sleep} seconds")
            await asyncio.sleep(self.bad_gateway_sleep)
            retries -= 1

    async def _send_message_direct(self, intent: IntentAPI, content: MessageEventContent,
                                   event_type: EventType = EventType.ROOM_MESSAGE, **kwargs
                                   ) -> EventID:
        if self.encrypted and self.matrix.e2ee:
            if intent.api.is_real_user:
                content[intent.api.real_user_content_key] = True
            event_type, content = await self.matrix.e2ee.encrypt(self.mxid, event_type, content)
        return await intent.send_message_event(self.mxid, event_type, content, **kwargs)

    @property
    @abstractmethod
    def bridge_info_state_key(self) -> str:
        pass

    @property
    @abstractmethod
    def bridge_info(self) -> Dict[str, Any]:
        pass

    # region Matrix room cleanup

    @abstractmethod
    async def delete(self) -> None:
        pass

    @classmethod
    async def cleanup_room(cls, intent: IntentAPI, room_id: RoomID, message: str = "Cleaning room",
                           puppets_only: bool = False) -> None:
        try:
            members = await intent.get_room_members(room_id)
        except MatrixError:
            members = []
        for user_id in members:
            puppet = await cls.bridge.get_puppet(user_id, create=False)
            if user_id != intent.mxid and (not puppets_only or puppet):
                try:
                    if puppet:
                        await puppet.intent.leave_room(room_id)
                    else:
                        await intent.kick_user(room_id, user_id, message)
                except MatrixError:
                    pass
        try:
            await intent.leave_room(room_id)
        except MatrixError:
            cls.log.warning(f"Failed to leave room {room_id} when cleaning up room", exc_info=True)

    async def cleanup_portal(self, message: str, puppets_only: bool = False) -> None:
        await self.cleanup_room(self.main_intent, self.mxid, message, puppets_only)
        await self.delete()

    async def unbridge(self) -> None:
        await self.cleanup_portal("Room unbridged", puppets_only=True)

    async def cleanup_and_delete(self) -> None:
        await self.cleanup_portal("Portal deleted")

    async def get_authenticated_matrix_users(self) -> List[UserID]:
        """
        Get the list of Matrix user IDs who can be bridged. This is used to determine if the portal
        is empty (and should be cleaned up) or not. Bridges should override this to check that the
        users are either logged in or the portal has a relaybot.
        """
        try:
            members = await self.main_intent.get_room_members(self.mxid)
        except MatrixRequestError:
            return []
        return [member for member in members
                if (not self.bridge.is_bridge_ghost(member)
                    and member != self.az.bot_mxid)]

    # endregion
