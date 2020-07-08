# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Tuple, Union, Optional, List, Dict, Callable, Awaitable, cast
import logging
import asyncio
import hashlib
import hmac

# We currently only support postgres, so we want an ImportError if asyncpg is not installed
import asyncpg

from mautrix.types import (Filter, RoomFilter, EventFilter, RoomEventFilter, StateFilter, EventType,
                           RoomID, Serializable, JSON, MessageEvent, UserID, EncryptedEvent,
                           EncryptedMegolmEventContent)
from mautrix.client import Client
from mautrix.crypto import OlmMachine, CryptoStore, StateStore, PgCryptoStore, EncryptionError
from mautrix.bridge.portal import BasePortal
from mautrix.bridge.db import UserProfile
from mautrix.util.async_db import Database
from mautrix.util.logging import TraceLogger

GetPortalFunc = Callable[[RoomID], Awaitable[BasePortal]]


class PgStateStore(StateStore):
    db: Database
    get_portal: GetPortalFunc

    def __init__(self, db: Database, get_portal: GetPortalFunc) -> None:
        self.db = db
        self.get_portal = get_portal

    async def is_encrypted(self, room_id: RoomID) -> bool:
        portal = await self.get_portal(room_id)
        return portal.encrypted if portal else False

    async def find_shared_rooms(self, user_id: UserID) -> List[RoomID]:
        rows = await self.db.fetch("SELECT room_id FROM mx_user_profile "
                                   "LEFT JOIN portal ON portal.mxid=mx_user_profile.room_id "
                                   "WHERE user_id=$1 AND portal.encrypted=true", user_id)
        return [row["room_id"] for row in rows]


class EncryptionManager:
    loop: asyncio.AbstractEventLoop
    log: TraceLogger = logging.getLogger("mau.bridge.e2ee")

    client: Client
    crypto: OlmMachine
    crypto_store: CryptoStore
    state_store: StateStore

    bot_mxid: UserID
    login_shared_secret: bytes
    _id_prefix: str
    _id_suffix: str
    _share_session_waiters: Dict[RoomID, List[asyncio.Future]]

    sync_task: asyncio.Future

    def __init__(self, bot_mxid: UserID, login_shared_secret: str, homeserver_address: str,
                 user_id_prefix: str, user_id_suffix: str, device_name: str, db_url: str,
                 get_portal: GetPortalFunc, loop: Optional[asyncio.AbstractEventLoop] = None
                 ) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.bot_mxid = bot_mxid
        self.device_name = device_name
        self._id_prefix = user_id_prefix
        self._id_suffix = user_id_suffix
        self._share_session_waiters = {}
        self.login_shared_secret = login_shared_secret.encode("utf-8")
        self.crypto_store = PgCryptoStore(None, "mautrix.bridge.e2ee", db_url, loop=self.loop)
        self.client = Client(base_url=homeserver_address, mxid=self.bot_mxid, loop=self.loop,
                             store=self.crypto_store)
        self.state_store = PgStateStore(cast(PgCryptoStore, self.crypto_store), get_portal)
        self.crypto = OlmMachine(self.client, self.crypto_store, self.state_store)

    async def share_session_lock(self, room_id: RoomID) -> bool:
        try:
            waiters = self._share_session_waiters[room_id]
        except KeyError:
            self._share_session_waiters[room_id] = []
            return True
        else:
            fut = self.loop.create_future()
            waiters.append(fut)
            await fut
            return False

    def share_session_unlock(self, room_id: RoomID) -> None:
        for fut in self._share_session_waiters[room_id]:
            fut.set_result(None)
        del self._share_session_waiters[room_id]

    def _ignore_user(self, user_id: str) -> bool:
        return (user_id.startswith(self._id_prefix) and user_id.endswith(self._id_suffix)
                and user_id != self.bot_mxid)

    async def encrypt(self, room_id: RoomID, event_type: EventType,
                      content: Union[Serializable, JSON]
                      ) -> Tuple[EventType, EncryptedMegolmEventContent]:
        try:
            encrypted = await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        except EncryptionError:
            self.log.debug("Got EncryptionError, sharing group session and trying again")
            if await self.share_session_lock(room_id):
                try:
                    users = UserProfile.all_except(room_id, self._id_prefix, self._id_suffix,
                                                   self.bot_mxid)
                    await self.crypto.share_group_session(room_id, [profile.user_id
                                                                    for profile in users])
                finally:
                    self.share_session_unlock(room_id)
            encrypted = await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        return EventType.ROOM_ENCRYPTED, encrypted

    async def decrypt(self, evt: EncryptedEvent) -> MessageEvent:
        decrypted = await self.crypto.decrypt_megolm_event(evt)
        self.log.trace("Decrypted event %s: %s", evt.event_id, decrypted)
        return decrypted

    async def start(self) -> None:
        self.log.debug("Logging in with bridge bot user")
        password = hmac.new(self.login_shared_secret, self.bot_mxid.encode("utf-8"),
                            hashlib.sha512).hexdigest()
        await self.crypto_store.start()
        device_id = await self.crypto_store.find_first_device_id()
        if device_id:
            self.log.debug(f"Found device ID in database: {device_id}")
        self.crypto_store.device_id = device_id
        await self.client.login(password=password, device_name=self.device_name,
                                device_id=device_id)
        if not device_id:
            self.crypto_store.device_id = self.client.device_id
            self.log.debug(f"Logged in with new device ID {self.client.device_id}")
        await self.crypto.load()
        self.sync_task = self.client.start(self._filter)
        self.log.info("End-to-bridge encryption support is enabled")

    async def stop(self) -> None:
        self.sync_task.cancel()
        await self.crypto_store.stop()

    @property
    def _filter(self) -> Filter:
        all_events = EventType.find("*")
        return Filter(
            account_data=EventFilter(types=[all_events]),
            presence=EventFilter(not_types=[all_events]),
            room=RoomFilter(
                include_leave=False,
                state=StateFilter(not_types=[all_events]),
                timeline=RoomEventFilter(not_types=[all_events]),
                account_data=RoomEventFilter(not_types=[all_events]),
                ephemeral=RoomEventFilter(not_types=[all_events]),
            ),
        )
