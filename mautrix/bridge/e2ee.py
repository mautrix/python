# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Tuple, Union, Optional
import logging
import asyncio
import hashlib
import hmac

from mautrix.types import (Filter, RoomFilter, EventFilter, RoomEventFilter, StateFilter, EventType,
                           RoomID, Serializable, JSON, MessageEvent, UserID, EncryptedEvent,
                           EncryptedMegolmEventContent, StateEvent)
from mautrix.errors import EncryptionError
from mautrix.client import Client, SyncStore
from mautrix.client.state_store.sqlalchemy import UserProfile
from mautrix.crypto import OlmMachine, CryptoStore, StateStore, PgCryptoStore, PickleCryptoStore
from mautrix.util.logging import TraceLogger

from .crypto_state_store import GetPortalFunc, PgCryptoStateStore, SQLCryptoStateStore

try:
    from mautrix.util.async_db import Database
except ImportError:
    Database = None


class EncryptionManager:
    loop: asyncio.AbstractEventLoop
    log: TraceLogger = logging.getLogger("mau.bridge.e2ee")

    client: Client
    crypto: OlmMachine
    crypto_store: Union[CryptoStore, SyncStore]
    crypto_db: Optional[Database]
    state_store: StateStore

    bot_mxid: UserID
    login_shared_secret: bytes
    _id_prefix: str
    _id_suffix: str

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
        self.login_shared_secret = login_shared_secret.encode("utf-8")
        pickle_key = "mautrix.bridge.e2ee"
        if db_url.startswith("postgres://"):
            if not PgCryptoStore or not PgCryptoStateStore:
                raise RuntimeError("Database URL is set to postgres, but asyncpg is not installed")
            self.crypto_db = Database(url=db_url, upgrade_table=PgCryptoStore.upgrade_table,
                                      log=logging.getLogger("mau.crypto.db"), loop=self.loop)
            self.crypto_store = PgCryptoStore("", pickle_key, self.crypto_db)
            self.state_store = PgCryptoStateStore(self.crypto_db, get_portal)
        elif db_url.startswith("pickle:///"):
            self.crypto_db = None
            self.crypto_store = PickleCryptoStore("", pickle_key, db_url[len("pickle:///"):])
            self.state_store = SQLCryptoStateStore(get_portal)
        else:
            raise RuntimeError("Unsupported database scheme")
        self.client = Client(base_url=homeserver_address, mxid=self.bot_mxid, loop=self.loop,
                             sync_store=self.crypto_store)
        self.crypto = OlmMachine(self.client, self.crypto_store, self.state_store)

    def _ignore_user(self, user_id: str) -> bool:
        return (user_id.startswith(self._id_prefix) and user_id.endswith(self._id_suffix)
                and user_id != self.bot_mxid)

    async def handle_member_event(self, evt: StateEvent) -> None:
        if self._ignore_user(evt.state_key):
            # We don't want to invalidate group sessions because a ghost left or joined
            return
        await self.crypto.handle_member_event(evt)

    async def encrypt(self, room_id: RoomID, event_type: EventType,
                      content: Union[Serializable, JSON]
                      ) -> Tuple[EventType, EncryptedMegolmEventContent]:
        try:
            encrypted = await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        except EncryptionError:
            self.log.debug("Got EncryptionError, sharing group session and trying again")
            if not self.crypto.is_sharing_group_session(room_id):
                # TODO if this becomes async, this should be locked separately
                #      instead of only relying on crypto.wait_group_session
                users = UserProfile.all_in_room(room_id, self._id_prefix, self._id_suffix,
                                                self.bot_mxid)
                await self.crypto.share_group_session(room_id, [profile.user_id
                                                                for profile in users])
            else:
                await self.crypto.wait_group_session(room_id)
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
        if self.crypto_db:
            await self.crypto_db.start()
        await self.crypto_store.open()
        device_id = await self.crypto_store.get_device_id()
        if device_id:
            self.log.debug(f"Found device ID in database: {device_id}")
        await self.client.login(password=password, device_name=self.device_name,
                                device_id=device_id, store_access_token=True, update_hs_url=False)
        await self.crypto.load()
        if not device_id:
            await self.crypto_store.put_device_id(self.client.device_id)
            self.log.debug(f"Logged in with new device ID {self.client.device_id}")
        self.sync_task = self.client.start(self._filter)
        self.log.info("End-to-bridge encryption support is enabled")

    async def stop(self) -> None:
        self.sync_task.cancel()
        await self.crypto_store.close()
        if self.crypto_db:
            await self.crypto_db.stop()

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
