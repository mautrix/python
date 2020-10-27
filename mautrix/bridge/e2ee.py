# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Tuple, Union, Optional, Dict, TYPE_CHECKING
import logging
import asyncio

from mautrix.types import (Filter, RoomFilter, EventFilter, RoomEventFilter, StateFilter, EventType,
                           RoomID, Serializable, JSON, MessageEvent, EncryptedEvent, StateEvent,
                           EncryptedMegolmEventContent, RequestedKeyInfo, RoomKeyWithheldCode,
                           LoginType)
from mautrix.appservice import AppService
from mautrix.errors import EncryptionError, SessionNotFound
from mautrix.client import Client, SyncStore
from mautrix.crypto import (OlmMachine, CryptoStore, StateStore, PgCryptoStore, PickleCryptoStore,
                            DeviceIdentity, RejectKeyShare, TrustState)
from mautrix.util.logging import TraceLogger

from .crypto_state_store import PgCryptoStateStore, SQLCryptoStateStore

try:
    from mautrix.client.state_store.sqlalchemy import UserProfile
except ImportError:
    UserProfile = None

try:
    from mautrix.util.async_db import Database
except ImportError:
    Database = None

if TYPE_CHECKING:
    from mautrix.bridge import Bridge


class EncryptionManager:
    loop: asyncio.AbstractEventLoop
    log: TraceLogger = logging.getLogger("mau.bridge.e2ee")

    client: Client
    crypto: OlmMachine
    crypto_store: Union[CryptoStore, SyncStore]
    crypto_db: Optional[Database]
    state_store: StateStore

    bridge: 'Bridge'
    az: AppService
    _id_prefix: str
    _id_suffix: str

    sync_task: asyncio.Future
    _share_session_events: Dict[RoomID, asyncio.Event]

    def __init__(self, bridge: 'Bridge', homeserver_address: str, user_id_prefix: str,
                 user_id_suffix: str, db_url: str, key_sharing_config: Dict[str, bool] = None
                 ) -> None:
        self.loop = bridge.loop or asyncio.get_event_loop()
        self.bridge = bridge
        self.az = bridge.az
        self.device_name = bridge.name
        self._id_prefix = user_id_prefix
        self._id_suffix = user_id_suffix
        self._share_session_events = {}
        self.key_sharing_config = key_sharing_config or {}
        pickle_key = "mautrix.bridge.e2ee"
        if db_url.startswith("postgres://"):
            if not PgCryptoStore or not PgCryptoStateStore:
                raise RuntimeError("Database URL is set to postgres, but asyncpg is not installed")
            self.crypto_db = Database(url=db_url, upgrade_table=PgCryptoStore.upgrade_table,
                                      log=logging.getLogger("mau.crypto.db"), loop=self.loop)
            self.crypto_store = PgCryptoStore("", pickle_key, self.crypto_db)
            self.state_store = PgCryptoStateStore(self.crypto_db, bridge.get_portal)
        elif db_url.startswith("pickle:///"):
            self.crypto_db = None
            self.crypto_store = PickleCryptoStore("", pickle_key, db_url[len("pickle:///"):])
            self.state_store = SQLCryptoStateStore(bridge.get_portal)
        else:
            raise RuntimeError("Unsupported database scheme")
        self.client = Client(base_url=homeserver_address, mxid=self.az.bot_mxid, loop=self.loop,
                             sync_store=self.crypto_store, log=self.log.getChild("client"))
        self.crypto = OlmMachine(self.client, self.crypto_store, self.state_store)
        self.crypto.allow_key_share = self.allow_key_share

    async def allow_key_share(self, device: DeviceIdentity, request: RequestedKeyInfo) -> bool:
        require_verification = self.key_sharing_config.get("require_verification", True)
        allow = self.key_sharing_config.get("allow", False)
        if not allow:
            self.log.debug(f"Key sharing not enabled, ignoring key request from "
                           f"{device.user_id}/{device.device_id}")
            return False
        elif device.trust == TrustState.BLACKLISTED:
            raise RejectKeyShare(f"Rejecting key request from blacklisted device "
                                 f"{device.user_id}/{device.device_id}",
                                 code=RoomKeyWithheldCode.BLACKLISTED,
                                 reason="You have been blacklisted by this device")
        elif device.trust == TrustState.VERIFIED or not require_verification:
            portal = await self.bridge.get_portal(request.room_id)
            if portal is None:
                raise RejectKeyShare(f"Rejecting key request for {request.session_id} from "
                                     f"{device.user_id}/{device.device_id}: room is not a portal",
                                     code=RoomKeyWithheldCode.UNAVAILABLE,
                                     reason="Requested room is not a portal")
            user = await self.bridge.get_user(device.user_id)
            if not await user.is_in_portal(portal):
                raise RejectKeyShare(f"Rejecting key request for {request.session_id} from "
                                     f"{device.user_id}/{device.device_id}: user is not in portal",
                                     code=RoomKeyWithheldCode.UNAUTHORIZED,
                                     reason="You're not in that portal")
            self.log.debug(f"Accepting key request for {request.session_id} from "
                           f"{device.user_id}/{device.device_id}")
            return True
        else:
            raise RejectKeyShare(f"Rejecting key request from unverified device "
                                 f"{device.user_id}/{device.device_id}",
                                 code=RoomKeyWithheldCode.UNVERIFIED,
                                 reason="You have not been verified by this device")

    def _ignore_user(self, user_id: str) -> bool:
        return (user_id.startswith(self._id_prefix) and user_id.endswith(self._id_suffix)
                and user_id != self.az.bot_mxid)

    async def handle_member_event(self, evt: StateEvent) -> None:
        if self._ignore_user(evt.state_key):
            # We don't want to invalidate group sessions because a ghost left or joined
            return
        await self.crypto.handle_member_event(evt)

    async def _share_session_lock(self, room_id: RoomID) -> bool:
        try:
            event = self._share_session_events[room_id]
        except KeyError:
            self._share_session_events[room_id] = asyncio.Event()
            return True
        else:
            await event.wait()
            return False

    async def encrypt(self, room_id: RoomID, event_type: EventType,
                      content: Union[Serializable, JSON]
                      ) -> Tuple[EventType, EncryptedMegolmEventContent]:
        try:
            encrypted = await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        except EncryptionError:
            self.log.debug("Got EncryptionError, sharing group session and trying again")
            if await self._share_session_lock(room_id):
                try:
                    users = await self.az.state_store.get_members_filtered(
                        room_id, self._id_prefix, self._id_suffix, self.az.bot_mxid)
                    await self.crypto.share_group_session(room_id, users)
                finally:
                    self._share_session_events.pop(room_id).set()
            encrypted = await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        return EventType.ROOM_ENCRYPTED, encrypted

    async def decrypt(self, evt: EncryptedEvent, wait_session_timeout: int = 5) -> MessageEvent:
        try:
            decrypted = await self.crypto.decrypt_megolm_event(evt)
        except SessionNotFound as e:
            if not wait_session_timeout:
                raise
            self.log.debug(f"Didn't find session {e.session_id},"
                           f" waiting {wait_session_timeout} seconds for session to arrive")
            got_keys = await self.crypto.wait_for_session(evt.room_id, e.sender_key, e.session_id,
                                                          timeout=wait_session_timeout)
            if got_keys:
                decrypted = await self.crypto.decrypt_megolm_event(evt)
            else:
                raise
        self.log.trace("Decrypted event %s: %s", evt.event_id, decrypted)
        return decrypted

    async def check_server_support(self) -> bool:
        flows = await self.client.get_login_flows()
        return flows.supports_type(LoginType.APPSERVICE)

    async def start(self) -> None:
        self.log.debug("Logging in with bridge bot user")
        if self.crypto_db:
            await self.crypto_db.start()
        await self.crypto_store.open()
        device_id = await self.crypto_store.get_device_id()
        if device_id:
            self.log.debug(f"Found device ID in database: {device_id}")
        # We set the API token to the AS token here to authenticate the appservice login
        # It'll get overridden after the login
        self.client.api.token = self.az.as_token
        await self.client.login(login_type=LoginType.APPSERVICE, device_name=self.device_name,
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
