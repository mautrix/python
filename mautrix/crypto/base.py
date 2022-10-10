# Copyright (c) 2022 Tulir Asokan
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

from mautrix.types import (
    DeviceID,
    EncryptionKeyAlgorithm,
    IdentityKey,
    KeyID,
    RequestedKeyInfo,
    RoomID,
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

    # Futures that wait for responses to a key request
    _key_request_waiters: dict[SessionID, asyncio.Future]
    # Futures that wait for a session to be received (either normally or through a key request)
    _inbound_session_waiters: dict[SessionID, asyncio.Future]

    _prev_unwedge: dict[IdentityKey, float]
    _fetch_keys_lock: asyncio.Lock
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
