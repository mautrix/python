# Copyright (c) 2023 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable, Callable, TypedDict
import asyncio
import functools
import json

import olm

from mautrix.errors import MForbidden, MNotFound
from mautrix.types import (
    DeviceID,
    EncryptionKeyAlgorithm,
    EventType,
    IdentityKey,
    KeyID,
    RequestedKeyInfo,
    RoomEncryptionStateEventContent,
    RoomID,
    RoomKeyEventContent,
    SessionID,
    SigningKey,
    TrustState,
    UserID,
)
from mautrix.util.logging import TraceLogger

from .. import client as cli, crypto


class SignedObject(TypedDict):
    signatures: dict[UserID, dict[str, str]]
    unsigned: Any


class BaseOlmMachine:
    client: cli.Client
    log: TraceLogger
    crypto_store: crypto.CryptoStore
    state_store: crypto.StateStore

    account: account.OlmAccount

    send_keys_min_trust: TrustState
    share_keys_min_trust: TrustState
    allow_key_share: Callable[[crypto.DeviceIdentity, RequestedKeyInfo], Awaitable[bool]]

    delete_outbound_keys_on_ack: bool
    dont_store_outbound_keys: bool
    delete_previous_keys_on_receive: bool
    ratchet_keys_on_decrypt: bool
    delete_fully_used_keys_on_decrypt: bool
    delete_keys_on_device_delete: bool
    disable_device_change_key_rotation: bool

    # Futures that wait for responses to a key request
    _key_request_waiters: dict[SessionID, asyncio.Future]
    # Futures that wait for a session to be received (either normally or through a key request)
    _inbound_session_waiters: dict[SessionID, asyncio.Future]

    _prev_unwedge: dict[IdentityKey, float]
    _fetch_keys_lock: asyncio.Lock
    _megolm_decrypt_lock: asyncio.Lock
    _share_keys_lock: asyncio.Lock
    _last_key_share: float
    _cs_fetch_attempted: set[UserID]

    async def wait_for_session(
        self, room_id: RoomID, session_id: SessionID, timeout: float = 3
    ) -> bool:
        try:
            fut = self._inbound_session_waiters[session_id]
        except KeyError:
            fut = asyncio.get_running_loop().create_future()
            self._inbound_session_waiters[session_id] = fut
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout)
        except asyncio.TimeoutError:
            return await self.crypto_store.has_group_session(room_id, session_id)

    def _mark_session_received(self, session_id: SessionID) -> None:
        try:
            self._inbound_session_waiters.pop(session_id).set_result(True)
        except KeyError:
            return

    async def _fill_encryption_info(self, evt: RoomKeyEventContent) -> None:
        encryption_info = await self.state_store.get_encryption_info(evt.room_id)
        if not encryption_info:
            self.log.warning(
                f"Encryption info for {evt.room_id} not found in state store, fetching from server"
            )
            try:
                encryption_info = await self.client.get_state_event(
                    evt.room_id, EventType.ROOM_ENCRYPTION
                )
            except (MNotFound, MForbidden) as e:
                self.log.warning(
                    f"Failed to get encryption info for {evt.room_id} from server: {e},"
                    " using defaults"
                )
                encryption_info = RoomEncryptionStateEventContent()
            if not encryption_info:
                self.log.warning(
                    f"Didn't find encryption info for {evt.room_id} on server either,"
                    " using defaults"
                )
                encryption_info = RoomEncryptionStateEventContent()

        if not evt.beeper_max_age_ms:
            evt.beeper_max_age_ms = encryption_info.rotation_period_ms
        if not evt.beeper_max_messages:
            evt.beeper_max_messages = encryption_info.rotation_period_msgs


canonical_json = functools.partial(
    json.dumps, ensure_ascii=False, separators=(",", ":"), sort_keys=True
)


def verify_signature_json(
    data: "SignedObject", user_id: UserID, key_name: DeviceID | str, key: SigningKey
) -> bool:
    data_copy = {**data}
    data_copy.pop("unsigned", None)
    signatures = data_copy.pop("signatures")
    key_id = str(KeyID(EncryptionKeyAlgorithm.ED25519, key_name))
    try:
        signature = signatures[user_id][key_id]
    except KeyError:
        return False
    signed_data = canonical_json(data_copy)
    try:
        olm.ed25519_verify(key, signed_data, signature)
        return True
    except olm.OlmVerifyError:
        return False
