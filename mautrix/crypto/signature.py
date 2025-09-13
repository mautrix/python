# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, TypedDict
import functools
import json

import olm

from mautrix.types import DeviceID, EncryptionKeyAlgorithm, KeyID, SigningKey, UserID

try:
    from Crypto.PublicKey import ECC
    from Crypto.Signature import eddsa
except ImportError:
    from Cryptodome.PublicKey import ECC
    from Cryptodome.Signature import eddsa

canonical_json = functools.partial(
    json.dumps, ensure_ascii=False, separators=(",", ":"), sort_keys=True
)


class SignedObject(TypedDict):
    signatures: dict[UserID, dict[str, str]]
    unsigned: Any


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
