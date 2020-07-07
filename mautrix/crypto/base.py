# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, TYPE_CHECKING
import functools
import json

import olm

from mautrix.types import UserID, DeviceID, SigningKey, EncryptionKeyAlgorithm
from mautrix.client import Client
from mautrix.util.logging import TraceLogger

if TYPE_CHECKING:
    from .store import CryptoStore, StateStore
    from .account import OlmAccount

    from typing import TypedDict, Dict


    class SignedObject(TypedDict):
        signatures: Dict[UserID, Dict[str, str]]
        unsigned: Any


class BaseOlmMachine:
    client: Client
    log: TraceLogger
    crypto_store: 'CryptoStore'
    state_store: 'StateStore'

    account: 'OlmAccount'

    allow_unverified_devices: bool


canonical_json = functools.partial(json.dumps, ensure_ascii=False, separators=(",", ":"),
                                   sort_keys=True)


def verify_signature_json(data: 'SignedObject', user_id: UserID, device_id: DeviceID,
                          key: SigningKey) -> bool:
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
