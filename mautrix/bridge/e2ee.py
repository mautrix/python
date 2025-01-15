# Copyright (c) 2022 Tulir Asokan
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
from mautrix.client import Client, InternalEventType, SyncStore
from mautrix.crypto import CryptoStore, OlmMachine, PgCryptoStore, RejectKeyShare, StateStore
from mautrix.errors import EncryptionError, MForbidden, MNotFound, SessionNotFound
from mautrix.types import (
    JSON,
    DeviceIdentity,
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
    TrustState,
)
from mautrix.util import background_task
from mautrix.util.async_db import Database
from mautrix.util.logging import TraceLogger

from .. import bridge as br
from .crypto_state_store import PgCryptoStateStore


class EncryptionManager:
    loop: asyncio.AbstractEventLoop
    log: TraceLogger = logging.getLogger("mau.bridge.e2ee")

    client: Client
    crypto: OlmMachine
    crypto_store: CryptoStore | SyncStore
    crypto_db: Database | None
    state_store: StateStore

    min_send_trust: TrustState
    key_sharing_enabled: bool
    appservice_mode: bool
    periodically_delete_expired_keys: bool
    delete_outdated_inbound: bool
    msc4190: bool

    bridge: br.Bridge
    az: AppService
    _id_prefix: str
    _id_suffix: str

    _share_session_events: dict[RoomID, asyncio.Event]
    _key_delete_task: asyncio.Task | None

    def __init__(
        self,
        bridge: br.Bridge,
        homeserver_address: str,
        user_id_prefix: str,
        user_id_suffix: str,
        db_url: str,
    ) -> None:
        self.loop = bridge.loop or asyncio.get_event_loop()
        self.bridge = bridge
        self.az = bridge.az
        self.device_name = bridge.name
        self._id_prefix = user_id_prefix
        self._id_suffix = user_id_suffix
        self._share_session_events = {}
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
            state_store=self.bridge.state_store,
        )
        self.crypto = OlmMachine(self.client, self.crypto_store, self.state_store)
        self.client.add_event_handler(InternalEventType.SYNC_STOPPED, self._exit_on_sync_fail)
        self.crypto.allow_key_share = self.allow_key_share
        verification_levels = bridge.config["bridge.encryption.verification_levels"]
        self.min_send_trust = TrustState.parse(verification_levels["send"])
        self.crypto.share_keys_min_trust = TrustState.parse(verification_levels["share"])
        self.crypto.send_keys_min_trust = TrustState.parse(verification_levels["receive"])
        self.key_sharing_enabled = bridge.config["bridge.encryption.allow_key_sharing"]
        self.appservice_mode = bridge.config["bridge.encryption.appservice"]
        self.msc4190 = bridge.config["bridge.encryption.msc4190"]
        if self.appservice_mode:
            self.az.otk_handler = self.crypto.handle_as_otk_counts
            self.az.device_list_handler = self.crypto.handle_as_device_lists
            self.az.to_device_handler = self.crypto.handle_as_to_device_event

        self.periodically_delete_expired_keys = False
        self.delete_outdated_inbound = False
        self._key_delete_task = None
        del_cfg = bridge.config["bridge.encryption.delete_keys"]
        if del_cfg:
            self.crypto.delete_outbound_keys_on_ack = del_cfg["delete_outbound_on_ack"]
            self.crypto.dont_store_outbound_keys = del_cfg["dont_store_outbound"]
            self.crypto.delete_previous_keys_on_receive = del_cfg["delete_prev_on_new_session"]
            self.crypto.ratchet_keys_on_decrypt = del_cfg["ratchet_on_decrypt"]
            self.crypto.delete_fully_used_keys_on_decrypt = del_cfg["delete_fully_used_on_decrypt"]
            self.crypto.delete_keys_on_device_delete = del_cfg["delete_on_device_delete"]
            self.periodically_delete_expired_keys = del_cfg["periodically_delete_expired"]
            self.delete_outdated_inbound = del_cfg["delete_outdated_inbound"]
        self.crypto.disable_device_change_key_rotation = bridge.config[
            "bridge.encryption.rotation.disable_device_change_key_rotation"
        ]

    async def _exit_on_sync_fail(self, data) -> None:
        if data["error"]:
            self.log.critical("Exiting due to crypto sync error")
            sys.exit(32)

    async def allow_key_share(self, device: DeviceIdentity, request: RequestedKeyInfo) -> bool:
        if not self.key_sharing_enabled:
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
                reason="Your device has been blacklisted by the bridge",
            )
        elif await self.crypto.resolve_trust(device) >= self.crypto.share_keys_min_trust:
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
                reason="Your device is not trusted by the bridge",
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
                evt.room_id, e.session_id, timeout=wait_session_timeout
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
        if not self.msc4190 and not flows.supports_type(LoginType.APPSERVICE):
            self.log.critical(
                "Encryption enabled in config, but homeserver does not support appservice login"
            )
            sys.exit(30)
        self.log.debug("Logging in with bridge bot user")
        if self.crypto_db:
            try:
                await self.crypto_db.start()
            except Exception as e:
                self.bridge._log_db_error(e)
        await self.crypto_store.open()
        device_id = await self.crypto_store.get_device_id()
        if device_id:
            self.log.debug(f"Found device ID in database: {device_id}")

        if self.msc4190:
            if not device_id:
                self.log.debug("Creating bot device with MSC4190")
            self.client.api.token = self.az.as_token
            await self.client.create_device_msc4190(
                device_id=device_id, initial_display_name=self.device_name
            )
        else:
            # We set the API token to the AS token here to authenticate the appservice login
            # It'll get overridden after the login
            self.client.api.token = self.az.as_token
            await self.client.login(
                login_type=LoginType.APPSERVICE,
                device_name=self.device_name,
                device_id=device_id,
                store_access_token=True,
                update_hs_url=False,
            )

        await self.crypto.load()
        if not device_id:
            await self.crypto_store.put_device_id(self.client.device_id)
            self.log.debug(f"Logged in with new device ID {self.client.device_id}")
        elif self.crypto.account.shared:
            await self._verify_keys_are_on_server()
        if self.appservice_mode:
            self.log.info("End-to-bridge encryption support is enabled (appservice mode)")
        else:
            _ = self.client.start(self._filter)
            self.log.info("End-to-bridge encryption support is enabled (sync mode)")
        if self.delete_outdated_inbound:
            deleted = await self.crypto_store.redact_outdated_group_sessions()
            if len(deleted) > 0:
                self.log.debug(
                    f"Deleted {len(deleted)} inbound keys which lacked expiration metadata"
                )
        if self.periodically_delete_expired_keys:
            self._key_delete_task = background_task.create(self._periodically_delete_keys())
        background_task.create(self._resync_encryption_info())

    async def _resync_encryption_info(self) -> None:
        rows = await self.crypto_db.fetch(
            """SELECT room_id FROM mx_room_state WHERE encryption='{"resync":true}'"""
        )
        room_ids = [row["room_id"] for row in rows]
        if not room_ids:
            return
        self.log.debug(f"Resyncing encryption state event in rooms: {room_ids}")
        for room_id in room_ids:
            try:
                evt = await self.client.get_state_event(room_id, EventType.ROOM_ENCRYPTION)
            except (MNotFound, MForbidden) as e:
                self.log.debug(f"Failed to get encryption state in {room_id}: {e}")
                q = """
                    UPDATE mx_room_state SET encryption=NULL
                    WHERE room_id=$1 AND encryption='{"resync":true}'
                """
                await self.crypto_db.execute(q, room_id)
            else:
                self.log.debug(f"Resynced encryption state in {room_id}: {evt}")
                q = """
                    UPDATE crypto_megolm_inbound_session SET max_age=$1, max_messages=$2
                    WHERE room_id=$3 AND max_age IS NULL and max_messages IS NULL
                """
                await self.crypto_db.execute(
                    q, evt.rotation_period_ms, evt.rotation_period_msgs, room_id
                )

    async def _verify_keys_are_on_server(self) -> None:
        self.log.debug("Making sure keys are still on server")
        try:
            resp = await self.client.query_keys([self.client.mxid])
        except Exception:
            self.log.critical(
                "Failed to query own keys to make sure device still exists", exc_info=True
            )
            sys.exit(33)
        try:
            own_keys = resp.device_keys[self.client.mxid][self.client.device_id]
            if len(own_keys.keys) > 0:
                return
        except KeyError:
            pass
        self.log.critical("Existing device doesn't have keys on server, resetting crypto")
        await self.crypto.crypto_store.delete()
        await self.client.logout_all()
        sys.exit(34)

    async def stop(self) -> None:
        if self._key_delete_task:
            self._key_delete_task.cancel()
            self._key_delete_task = None
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

    async def _periodically_delete_keys(self) -> None:
        while True:
            deleted = await self.crypto_store.redact_expired_group_sessions()
            if deleted:
                self.log.info(f"Deleted expired megolm sessions: {deleted}")
            else:
                self.log.debug("No expired megolm sessions found")
            await asyncio.sleep(24 * 60 * 60)
