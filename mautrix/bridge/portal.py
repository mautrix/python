# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
import asyncio
import logging

from mautrix.appservice import AppService, IntentAPI
from mautrix.types import (RoomID, EventID, MessageEventContent, EventType, EncryptionAlgorithm,
                           RoomEncryptionStateEventContent as Encryption)
from mautrix.util.logging import TraceLogger

if TYPE_CHECKING:
    from .user import BaseUser


class BasePortal(ABC):
    log: TraceLogger = logging.getLogger("mau.portal")
    az: AppService
    loop: asyncio.AbstractEventLoop
    main_intent: IntentAPI
    mxid: Optional[RoomID]
    encrypted: bool

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
