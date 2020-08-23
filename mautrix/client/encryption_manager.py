# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Set, Optional, Dict, TYPE_CHECKING
import logging
import asyncio

from mautrix.types import (RoomID, EventID, EventType, EventContent, EncryptedMegolmEventContent,
                           EncryptedEvent)
from mautrix.errors import MNotFound, EncryptionError, DecryptionError
from mautrix.util.logging import TraceLogger

from .store_updater import StoreUpdatingAPI
from .dispatcher import SimpleDispatcher

if TYPE_CHECKING:
    from mautrix.crypto import OlmMachine
    from .client import Client


class EncryptingAPI(StoreUpdatingAPI):
    _crypto: Optional['OlmMachine']
    encryption_blacklist: Set[EventType] = {EventType.REACTION}
    crypto_log: TraceLogger = logging.getLogger("mau.client.crypto")
    _share_session_events: Dict[RoomID, asyncio.Event]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._crypto = None
        self._share_session_events = {}

    @property
    def crypto(self) -> Optional['OlmMachine']:
        return self._crypto

    @crypto.setter
    def crypto(self, crypto: 'OlmMachine') -> None:
        if not self.state_store:
            raise ValueError("State store must be set to use encryption")
        self._crypto = crypto

    @property
    def crypto_enabled(self) -> bool:
        return bool(self.crypto) and bool(self.state_store)

    async def encrypt(self, room_id: RoomID, event_type: EventType, content: EventContent
                      ) -> EncryptedMegolmEventContent:
        try:
            return await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        except EncryptionError:
            self.crypto_log.debug("Got EncryptionError, sharing group session and trying again")
            await self.share_group_session(room_id)
            self.crypto_log.trace(f"Shared group session, now trying to encrypt in {room_id} again")
            return await self.crypto.encrypt_megolm_event(room_id, event_type, content)

    async def _share_session_lock(self, room_id: RoomID) -> bool:
        try:
            event = self._share_session_events[room_id]
        except KeyError:
            self._share_session_events[room_id] = asyncio.Event()
            return True
        else:
            await event.wait()
            return False

    async def share_group_session(self, room_id: RoomID) -> None:
        if not await self._share_session_lock(room_id):
            self.log.silly("Group session was already being shared, so didn't share new one")
            return
        try:
            if not await self.state_store.has_full_member_list(room_id):
                self.crypto_log.trace(f"Don't have full member list for {room_id},"
                                      " fetching from server")
                members = list((await self.get_joined_members(room_id)).keys())
            else:
                self.crypto_log.trace(f"Fetching member list for {room_id} from state store")
                members = await self.state_store.get_members(room_id)
            await self.crypto.share_group_session(room_id, members)
        finally:
            self._share_session_events.pop(room_id).set()

    async def send_message_event(self, room_id: RoomID, event_type: EventType,
                                 content: EventContent, disable_encryption: bool = False,
                                 **kwargs) -> EventID:
        if self.crypto and event_type not in self.encryption_blacklist and not disable_encryption:
            is_encrypted = await self.state_store.is_encrypted(room_id)
            if is_encrypted is None:
                try:
                    await self.get_state_event(room_id, EventType.ROOM_ENCRYPTION)
                    is_encrypted = True
                except MNotFound:
                    is_encrypted = False
            if is_encrypted:
                content = await self.encrypt(room_id, event_type, content)
                event_type = EventType.ROOM_ENCRYPTED
        return await super().send_message_event(room_id, event_type, content, **kwargs)


class DecryptionDispatcher(SimpleDispatcher):
    event_type = EventType.ROOM_ENCRYPTED
    client: 'Client'

    async def handle(self, evt: EncryptedEvent) -> None:
        try:
            self.client.crypto_log.trace(f"Decrypting {evt.event_id} in {evt.room_id}...")
            decrypted = await self.client.crypto.decrypt_megolm_event(evt)
        except DecryptionError as e:
            self.client.crypto_log.warning(f"Failed to decrypt {evt.event_id}: {e}")
            return
        self.client.crypto_log.trace(f"Decrypted {evt.event_id}: {decrypted}")
        self.client.dispatch_event(decrypted, evt.source)
