# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict
import asyncio
import functools
import json
import sys

import olm

from mautrix.types import (
    DeviceID,
    EncryptionKeyAlgorithm,
    IdentityKey,
    RequestedKeyInfo,
    RoomID,
    SessionID,
    SigningKey,
    UserID,
)
from mautrix.util.logging import TraceLogger

from .. import client as cli
from .. import crypto

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class SignedObject(TypedDict):
    signatures: Dict[UserID, Dict[str, str]]
    unsigned: Any


class BaseOlmMachine:
    client: cli.Client
    log: TraceLogger
    crypto_store: crypto.CryptoStore
    state_store: crypto.StateStore

    account: account.OlmAccount

    allow_unverified_devices: bool
    share_to_unverified_devices: bool
    allow_key_share: Callable[[crypto.DeviceIdentity, RequestedKeyInfo], Awaitable[bool]]

    # Futures that wait for responses to a key request
    _key_request_waiters: Dict[SessionID, asyncio.Future]
    # Futures that wait for a session to be received (either normally or through a key request)
    _inbound_session_waiters: Dict[SessionID, asyncio.Future]

    _prev_unwedge: Dict[IdentityKey, float]

    async def wait_for_session(
        self, room_id: RoomID, sender_key: IdentityKey, session_id: SessionID, timeout: float = 3
    ) -> bool:
        try:
            fut = self._inbound_session_waiters[session_id]
        except KeyError:
            fut = asyncio.get_running_loop().create_future()
            self._inbound_session_waiters[session_id] = fut
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout)
        except asyncio.TimeoutError:
            return await self.crypto_store.has_group_session(room_id, sender_key, session_id)

    def _mark_session_received(self, session_id: SessionID) -> None:
        try:
            self._inbound_session_waiters.pop(session_id).set_result(True)
        except KeyError:
            return


canonical_json = functools.partial(
    json.dumps, ensure_ascii=False, separators=(",", ":"), sort_keys=True
)


def verify_signature_json(
    data: "SignedObject", user_id: UserID, device_id: DeviceID, key: SigningKey
) -> bool:
    data_copy = {**data}
    data_copy.pop("unsigned", None)
    signatures = data_copy.pop("signatures")
    signature = signatures[user_id][f"{EncryptionKeyAlgorithm.ED25519}:{device_id}"]
    signed_data = canonical_json(data_copy)
    try:
        olm.ed25519_verify(key, signed_data, signature)
        return True
    except olm.OlmVerifyError:
        return False
