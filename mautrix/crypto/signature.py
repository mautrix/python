# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, TypedDict
import functools
import json

import olm
import unpaddedbase64

from mautrix.types import (
    JSON,
    DeviceID,
    EncryptionKeyAlgorithm,
    KeyID,
    Serializable,
    Signature,
    SigningKey,
    UserID,
)

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


def sign_olm(data: dict[str, JSON] | Serializable, key: olm.PkSigning | olm.Account) -> Signature:
    if isinstance(data, Serializable):
        data = data.serialize()
    data.pop("signatures", None)
    data.pop("unsigned", None)
    return Signature(key.sign(canonical_json(data)))


def verify_signature_json(
    data: "SignedObject", user_id: UserID, key_name: DeviceID | str, key: SigningKey
) -> bool:
    data_copy = {**data}
    data_copy.pop("unsigned", None)
    signatures = data_copy.pop("signatures")
    key_id = str(KeyID(EncryptionKeyAlgorithm.ED25519, key_name))
    try:
        signature = signatures[user_id][key_id]
        decoded_key = unpaddedbase64.decode_base64(key)
        # pycryptodome doesn't accept raw keys, so wrap it in a DER structure
        der_key = b"\x30\x2a\x30\x05\x06\x03\x2b\x65\x70\x03\x21\x00" + decoded_key
        decoded_signature = unpaddedbase64.decode_base64(signature)
        parsed_key = ECC.import_key(der_key)
        verifier = eddsa.new(parsed_key, "rfc8032")
        verifier.verify(canonical_json(data_copy).encode("utf-8"), decoded_signature)
        return True
    except (KeyError, ValueError):
        return False
