# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import asyncio
import logging
import sys

from mautrix import __optional_imports__
from mautrix.appservice import AppService
from mautrix.client import Client, SyncStore
from mautrix.crypto import (
    CryptoStore,
    DeviceIdentity,
    OlmMachine,
    PgCryptoStore,
    RejectKeyShare,
    StateStore,
    TrustState,
)
from mautrix.errors import EncryptionError, SessionNotFound
from mautrix.types import (
    JSON,
    EncryptedEvent,
    EncryptedMegolmEventContent,
    EventFilter,
    EventType,
    Filter,
    LoginType,
    MessageEvent,
    RequestedKeyInfo,
    RoomEventFilter,
    RoomFilter,
    RoomID,
    RoomKeyWithheldCode,
    Serializable,
    StateEvent,
    StateFilter,
)
from mautrix.util.logging import TraceLogger

from .. import bridge as br
from .crypto_state_store import PgCryptoStateStore

try:
    from mautrix.client.state_store.sqlalchemy import UserProfile
except ImportError:
    if __optional_imports__:
        raise
    UserProfile = None

try:
    from mautrix.util.async_db import Database
except ImportError:
    if __optional_imports__:
        raise
    Database = None


class EncryptionManager:
    loop: asyncio.AbstractEventLoop
    log: TraceLogger = logging.getLogger("mau.bridge.e2ee")

    client: Client
    crypto: OlmMachine
    crypto_store: CryptoStore | SyncStore
    crypto_db: Database | None
    state_store: StateStore

    bridge: br.Bridge
    az: AppService
    _id_prefix: str
    _id_suffix: str

    _share_session_events: dict[RoomID, asyncio.Event]

    def __init__(
        self,
        bridge: br.Bridge,
        homeserver_address: str,
        user_id_prefix: str,
        user_id_suffix: str,
        db_url: str,
        key_sharing_config: dict[str, bool] = None,
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
        self.crypto_db = Database.create(
            url=db_url,
            upgrade_table=PgCryptoStore.upgrade_table,
            log=logging.getLogger("mau.crypto.db"),
        )
        self.crypto_store = PgCryptoStore("", pickle_key, self.crypto_db)
        self.state_store = PgCryptoStateStore(self.crypto_db, bridge.get_portal)
        default_http_retry_count = bridge.config.get("homeserver.http_retry_count", None)
        self.client = Client(
            base_url=homeserver_address,
            mxid=self.az.bot_mxid,
            loop=self.loop,
            sync_store=self.crypto_store,
            log=self.log.getChild("client"),
            default_retry_count=default_http_retry_count,
        )
        self.crypto = OlmMachine(self.client, self.crypto_store, self.state_store)
        self.crypto.allow_key_share = self.allow_key_share

    async def allow_key_share(self, device: DeviceIdentity, request: RequestedKeyInfo) -> bool:
        require_verification = self.key_sharing_config.get("require_verification", True)
        allow = self.key_sharing_config.get("allow", False)
        if not allow:
            self.log.debug(
                f"Key sharing not enabled, ignoring key request from "
                f"{device.user_id}/{device.device_id}"
            )
            return False
        elif device.trust == TrustState.BLACKLISTED:
            raise RejectKeyShare(
                f"Rejecting key request from blacklisted device "
                f"{device.user_id}/{device.device_id}",
                code=RoomKeyWithheldCode.BLACKLISTED,
                reason="You have been blacklisted by this device",
            )
        elif device.trust == TrustState.VERIFIED or not require_verification:
            portal = await self.bridge.get_portal(request.room_id)
            if portal is None:
                raise RejectKeyShare(
                    f"Rejecting key request for {request.session_id} from "
                    f"{device.user_id}/{device.device_id}: room is not a portal",
                    code=RoomKeyWithheldCode.UNAVAILABLE,
                    reason="Requested room is not a portal",
                )
            user = await self.bridge.get_user(device.user_id)
            if not await user.is_in_portal(portal):
                raise RejectKeyShare(
                    f"Rejecting key request for {request.session_id} from "
                    f"{device.user_id}/{device.device_id}: user is not in portal",
                    code=RoomKeyWithheldCode.UNAUTHORIZED,
                    reason="You're not in that portal",
                )
            self.log.debug(
                f"Accepting key request for {request.session_id} from "
                f"{device.user_id}/{device.device_id}"
            )
            return True
        else:
            raise RejectKeyShare(
                f"Rejecting key request from unverified device "
                f"{device.user_id}/{device.device_id}",
                code=RoomKeyWithheldCode.UNVERIFIED,
                reason="You have not been verified by this device",
            )

    def _ignore_user(self, user_id: str) -> bool:
        return (
            user_id.startswith(self._id_prefix)
            and user_id.endswith(self._id_suffix)
            and user_id != self.az.bot_mxid
        )

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

    async def encrypt(
        self, room_id: RoomID, event_type: EventType, content: Serializable | JSON
    ) -> tuple[EventType, EncryptedMegolmEventContent]:
        try:
            encrypted = await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        except EncryptionError:
            self.log.debug("Got EncryptionError, sharing group session and trying again")
            if await self._share_session_lock(room_id):
                try:
                    users = await self.az.state_store.get_members_filtered(
                        room_id, self._id_prefix, self._id_suffix, self.az.bot_mxid
                    )
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
            self.log.debug(
                f"Couldn't find session {e.session_id} trying to decrypt {evt.event_id},"
                f" waiting {wait_session_timeout} seconds..."
            )
            got_keys = await self.crypto.wait_for_session(
                evt.room_id, e.sender_key, e.session_id, timeout=wait_session_timeout
            )
            if got_keys:
                self.log.debug(
                    f"Got session {e.session_id} after waiting, "
                    f"trying to decrypt {evt.event_id} again"
                )
                decrypted = await self.crypto.decrypt_megolm_event(evt)
            else:
                raise
        self.log.trace("Decrypted event %s: %s", evt.event_id, decrypted)
        return decrypted

    async def start(self) -> None:
        flows = await self.client.get_login_flows()
        flow = flows.get_first_of_type(LoginType.APPSERVICE, LoginType.UNSTABLE_APPSERVICE)
        if flow is None:
            self.log.critical(
                "Encryption enabled in config, but homeserver does not "
                "advertise appservice login"
            )
            sys.exit(30)
        self.log.debug(f"Logging in with bridge bot user (using login type {flow.type.value})")
        if self.crypto_db:
            await self.crypto_db.start()
        await self.crypto_store.open()
        device_id = await self.crypto_store.get_device_id()
        if device_id:
            self.log.debug(f"Found device ID in database: {device_id}")
        # We set the API token to the AS token here to authenticate the appservice login
        # It'll get overridden after the login
        self.client.api.token = self.az.as_token
        await self.client.login(
            login_type=flow.type,
            device_name=self.device_name,
            device_id=device_id,
            store_access_token=True,
            update_hs_url=False,
        )
        await self.crypto.load()
        if not device_id:
            await self.crypto_store.put_device_id(self.client.device_id)
            self.log.debug(f"Logged in with new device ID {self.client.device_id}")
        _ = self.client.start(self._filter)
        self.log.info("End-to-bridge encryption support is enabled")

    async def stop(self) -> None:
        self.client.stop()
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
