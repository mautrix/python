# Copyright (c) 2023 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Optional
import asyncio
import logging
import time

from mautrix import client as cli
from mautrix.errors import GroupSessionWithheldError
from mautrix.types import (
    ASToDeviceEvent,
    DecryptedOlmEvent,
    DeviceID,
    DeviceLists,
    DeviceOTKCount,
    EncryptionAlgorithm,
    EncryptionKeyAlgorithm,
    EventType,
    Member,
    Membership,
    StateEvent,
    ToDeviceEvent,
    TrustState,
    UserID,
)
from mautrix.util import background_task
from mautrix.util.logging import TraceLogger

from .account import OlmAccount
from .decrypt_megolm import MegolmDecryptionMachine
from .encrypt_megolm import MegolmEncryptionMachine
from .key_request import KeyRequestingMachine
from .key_share import KeySharingMachine
from .store import CryptoStore, StateStore
from .unwedge import OlmUnwedgingMachine


class OlmMachine(
    MegolmEncryptionMachine,
    MegolmDecryptionMachine,
    OlmUnwedgingMachine,
    KeySharingMachine,
    KeyRequestingMachine,
):
    """
    OlmMachine is the main class for handling things related to Matrix end-to-end encryption with
    Olm and Megolm. Users primarily need :meth:`encrypt_megolm_event`, :meth:`share_group_session`,
    and :meth:`decrypt_megolm_event`. Tracking device lists, establishing Olm sessions and handling
    Megolm group sessions is handled internally.
    """

    client: cli.Client
    log: TraceLogger
    crypto_store: CryptoStore
    state_store: StateStore

    account: Optional[OlmAccount]

    def __init__(
        self,
        client: cli.Client,
        crypto_store: CryptoStore,
        state_store: StateStore,
        log: Optional[TraceLogger] = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.log = log or logging.getLogger("mau.crypto")
        self.crypto_store = crypto_store
        self.state_store = state_store
        self.account = None

        self.send_keys_min_trust = TrustState.UNVERIFIED
        self.share_keys_min_trust = TrustState.CROSS_SIGNED_TOFU
        self.allow_key_share = self.default_allow_key_share

        self.delete_outbound_keys_on_ack = False
        self.dont_store_outbound_keys = False
        self.delete_previous_keys_on_receive = False
        self.ratchet_keys_on_decrypt = False
        self.delete_fully_used_keys_on_decrypt = False
        self.delete_keys_on_device_delete = False
        self.disable_device_change_key_rotation = False

        self._fetch_keys_lock = asyncio.Lock()
        self._megolm_decrypt_lock = asyncio.Lock()
        self._share_keys_lock = asyncio.Lock()
        self._last_key_share = time.monotonic() - 60
        self._key_request_waiters = {}
        self._inbound_session_waiters = {}
        self._prev_unwedge = {}
        self._cs_fetch_attempted = set()

        self.client.add_event_handler(
            cli.InternalEventType.DEVICE_OTK_COUNT, self.handle_otk_count, wait_sync=True
        )
        self.client.add_event_handler(cli.InternalEventType.DEVICE_LISTS, self.handle_device_lists)
        self.client.add_event_handler(EventType.TO_DEVICE_ENCRYPTED, self.handle_to_device_event)
        self.client.add_event_handler(EventType.ROOM_KEY_REQUEST, self.handle_room_key_request)
        self.client.add_event_handler(EventType.BEEPER_ROOM_KEY_ACK, self.handle_beep_room_key_ack)
        # self.client.add_event_handler(EventType.ROOM_KEY_WITHHELD, self.handle_room_key_withheld)
        # self.client.add_event_handler(EventType.ORG_MATRIX_ROOM_KEY_WITHHELD,
        #                               self.handle_room_key_withheld)
        self.client.add_event_handler(EventType.ROOM_MEMBER, self.handle_member_event)

    async def load(self) -> None:
        """Load the Olm account into memory, or create one if the store doesn't have one stored."""
        self.account = await self.crypto_store.get_account()
        if self.account is None:
            self.account = OlmAccount()
            await self.crypto_store.put_account(self.account)

    async def handle_as_otk_counts(
        self, otk_counts: dict[UserID, dict[DeviceID, DeviceOTKCount]]
    ) -> None:
        for user_id, devices in otk_counts.items():
            for device_id, count in devices.items():
                if user_id == self.client.mxid and device_id == self.client.device_id:
                    await self.handle_otk_count(count)
                else:
                    self.log.warning(f"Got OTK count for unknown device {user_id}/{device_id}")

    async def handle_as_device_lists(self, device_lists: DeviceLists) -> None:
        background_task.create(self.handle_device_lists(device_lists))

    async def handle_as_to_device_event(self, evt: ASToDeviceEvent) -> None:
        if evt.to_user_id != self.client.mxid or evt.to_device_id != self.client.device_id:
            self.log.warning(
                f"Got to-device event for unknown device {evt.to_user_id}/{evt.to_device_id}"
            )
            return
        if evt.type == EventType.TO_DEVICE_ENCRYPTED:
            await self.handle_to_device_event(evt)
        elif evt.type == EventType.ROOM_KEY_REQUEST:
            await self.handle_room_key_request(evt)
        elif evt.type == EventType.BEEPER_ROOM_KEY_ACK:
            await self.handle_beep_room_key_ack(evt)
        else:
            self.log.debug(f"Got unknown to-device event {evt.type} from {evt.sender}")

    async def handle_otk_count(self, otk_count: DeviceOTKCount) -> None:
        """
        Handle the ``device_one_time_keys_count`` data in a sync response.

        This is automatically registered as an event handler and therefore called if the client you
        passed to the OlmMachine is syncing. You shouldn't need to call this yourself unless you
        do syncing in some manual way.
        """
        if otk_count.signed_curve25519 < self.account.max_one_time_keys // 2:
            self.log.debug(
                f"Sync response said we have {otk_count.signed_curve25519} signed"
                " curve25519 keys left, sharing new ones..."
            )
            await self.share_keys(otk_count.signed_curve25519)

    async def handle_device_lists(self, device_lists: DeviceLists) -> None:
        """
        Handle the ``device_lists`` data in a sync response.

        This is automatically registered as an event handler and therefore called if the client you
        passed to the OlmMachine is syncing. You shouldn't need to call this yourself unless you
        do syncing in some manual way.
        """
        if len(device_lists.changed) > 0:
            async with self._fetch_keys_lock:
                await self._fetch_keys(device_lists.changed, include_untracked=False)

    async def handle_member_event(self, evt: StateEvent) -> None:
        """
        Handle a new member event.

        This is automatically registered as an event handler and therefore called if the client you
        passed to the OlmMachine is syncing. You shouldn't need to call this yourself unless you
        receive events in some manual way (e.g. through appservice transactions)
        """
        if not await self.state_store.is_encrypted(evt.room_id):
            return
        prev = evt.prev_content.membership
        cur = evt.content.membership
        ignored_changes = {
            Membership.INVITE: Membership.JOIN,
            Membership.BAN: Membership.LEAVE,
            Membership.LEAVE: Membership.BAN,
        }
        if prev == cur or ignored_changes.get(prev) == cur:
            return
        src = getattr(evt, "source", None)
        prev_cache = evt.unsigned.get("mautrix_prev_membership")
        if isinstance(prev_cache, Member) and prev_cache.membership == cur:
            self.log.debug(
                f"Got duplicate membership state event in {evt.room_id} changing {evt.state_key} "
                f"from {prev} to {cur}, cached state was {prev_cache} (event ID: {evt.event_id}, "
                f"sync source: {src})"
            )
            return
        self.log.debug(
            f"Got membership state event in {evt.room_id} changing {evt.state_key} from "
            f"{prev} to {cur} (event ID: {evt.event_id}, sync source: {src}, "
            f"cached: {prev_cache.membership if prev_cache else None}), invalidating group session"
        )
        await self.crypto_store.remove_outbound_group_session(evt.room_id)

    async def handle_to_device_event(self, evt: ToDeviceEvent) -> None:
        """
        Handle an encrypted to-device event.

        This is automatically registered as an event handler and therefore called if the client you
        passed to the OlmMachine is syncing. You shouldn't need to call this yourself unless you
        do syncing in some manual way.
        """
        self.log.trace(
            f"Handling encrypted to-device event from {evt.content.sender_key} ({evt.sender})"
        )
        decrypted_evt = await self._decrypt_olm_event(evt)
        if decrypted_evt.type == EventType.ROOM_KEY:
            await self._receive_room_key(decrypted_evt)
        elif decrypted_evt.type == EventType.FORWARDED_ROOM_KEY:
            await self._receive_forwarded_room_key(decrypted_evt)

    async def _receive_room_key(self, evt: DecryptedOlmEvent) -> None:
        # TODO nio had a comment saying "handle this better"
        #      for the case where evt.Keys.Ed25519 is none?
        if evt.content.algorithm != EncryptionAlgorithm.MEGOLM_V1 or not evt.keys.ed25519:
            return
        if not evt.content.beeper_max_messages or not evt.content.beeper_max_age_ms:
            await self._fill_encryption_info(evt.content)
        if self.delete_previous_keys_on_receive and not evt.content.beeper_is_scheduled:
            removed_ids = await self.crypto_store.redact_group_sessions(
                evt.content.room_id, evt.sender_key, reason="received new key from device"
            )
            self.log.info(f"Redacted previous megolm sessions: {removed_ids}")
        await self._create_group_session(
            evt.sender_key,
            evt.keys.ed25519,
            evt.content.room_id,
            evt.content.session_id,
            evt.content.session_key,
            max_age=evt.content.beeper_max_age_ms,
            max_messages=evt.content.beeper_max_messages,
            is_scheduled=evt.content.beeper_is_scheduled,
        )

    async def handle_beep_room_key_ack(self, evt: ToDeviceEvent) -> None:
        try:
            sess = await self.crypto_store.get_group_session(
                evt.content.room_id, evt.content.session_id
            )
        except GroupSessionWithheldError:
            self.log.debug(
                f"Ignoring room key ack for session {evt.content.session_id}"
                " that was already redacted"
            )
            return
        if not sess:
            self.log.debug(f"Ignoring room key ack for unknown session {evt.content.session_id}")
            return
        if (
            sess.sender_key == self.account.identity_key
            and self.delete_outbound_keys_on_ack
            and evt.content.first_message_index == 0
        ):
            self.log.debug("Redacting inbound copy of outbound group session after ack")
            await self.crypto_store.redact_group_session(
                evt.content.room_id, evt.content.session_id, reason="outbound session acked"
            )
        else:
            self.log.debug(f"Received room key ack for {sess.id}")

    async def share_keys(self, current_otk_count: int | None = None) -> None:
        """
        Share any keys that need to be shared. This is automatically called from
        :meth:`handle_otk_count`, so you should not need to call this yourself.

        Args:
            current_otk_count: The current number of signed curve25519 keys present on the server.
                If omitted, the count will be fetched from the server.
        """
        async with self._share_keys_lock:
            await self._share_keys(current_otk_count)

    async def _share_keys(self, current_otk_count: int | None) -> None:
        if current_otk_count is None or (
            # If the last key share was recent and the new count is very low, re-check the count
            # from the server to avoid any race conditions.
            self._last_key_share + 60 > time.monotonic()
            and current_otk_count < 10
        ):
            self.log.debug("Checking OTK count on server")
            current_otk_count = (await self.client.upload_keys()).get(
                EncryptionKeyAlgorithm.SIGNED_CURVE25519, 0
            )
        device_keys = (
            self.account.get_device_keys(self.client.mxid, self.client.device_id)
            if not self.account.shared
            else None
        )
        one_time_keys = self.account.get_one_time_keys(
            self.client.mxid, self.client.device_id, current_otk_count
        )
        if not device_keys and not one_time_keys:
            self.log.warning("No one-time keys nor device keys got when trying to share keys")
            return
        if device_keys:
            self.log.debug("Going to upload initial account keys")
        self.log.debug(f"Uploading {len(one_time_keys)} one-time keys")
        resp = await self.client.upload_keys(one_time_keys=one_time_keys, device_keys=device_keys)
        self.account.shared = True
        self._last_key_share = time.monotonic()
        await self.crypto_store.put_account(self.account)
        self.log.debug(f"Shared keys and saved account, new keys: {resp}")
