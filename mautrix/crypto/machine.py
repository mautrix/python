# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Optional
import asyncio
import logging

from mautrix import client as cli
from mautrix.types import (
    DeviceLists,
    DeviceOTKCount,
    EncryptionAlgorithm,
    EventType,
    Membership,
    StateEvent,
    ToDeviceEvent,
)
from mautrix.util.logging import TraceLogger

from .account import OlmAccount
from .decrypt_megolm import MegolmDecryptionMachine
from .encrypt_megolm import MegolmEncryptionMachine
from .key_request import KeyRequestingMachine
from .key_share import KeySharingMachine
from .store import CryptoStore, StateStore
from .types import DecryptedOlmEvent
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

    _fetch_keys_lock: asyncio.Lock

    account: Optional[OlmAccount]

    allow_unverified_devices: bool

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

        self.allow_unverified_devices = True
        self.share_to_unverified_devices = False
        self.allow_key_share = self.default_allow_key_share

        self._fetch_keys_lock = asyncio.Lock()
        self._key_request_waiters = {}
        self._inbound_session_waiters = {}
        self._prev_unwedge = {}

        self.client.add_event_handler(
            cli.InternalEventType.DEVICE_OTK_COUNT, self.handle_otk_count, wait_sync=True
        )
        self.client.add_event_handler(cli.InternalEventType.DEVICE_LISTS, self.handle_device_lists)
        self.client.add_event_handler(EventType.TO_DEVICE_ENCRYPTED, self.handle_to_device_event)
        self.client.add_event_handler(EventType.ROOM_KEY_REQUEST, self.handle_room_key_request)
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
        self.log.debug(
            f"Got membership state event in {evt.room_id} changing {evt.state_key} from "
            f"{prev} to {cur}, invalidating group session"
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
        await self._create_group_session(
            evt.sender_key,
            evt.keys.ed25519,
            evt.content.room_id,
            evt.content.session_id,
            evt.content.session_key,
        )

    async def share_keys(self, current_otk_count: int) -> None:
        """
        Share any keys that need to be shared. This is automatically called from
        :meth:`handle_otk_count`, so you should not need to call this yourself.

        Args:
            current_otk_count: The current number of signed curve25519 keys present on the server.
        """
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
        await self.client.upload_keys(one_time_keys=one_time_keys, device_keys=device_keys)
        self.account.shared = True
        await self.crypto_store.put_account(self.account)
        self.log.debug("Shared keys and saved account")
