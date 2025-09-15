# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import hashlib
import hmac

import base58
import unpaddedbase64

from mautrix.types import EventType

try:
    from Crypto import Random
    from Crypto.Cipher import AES
    from Crypto.Hash import SHA256
    from Crypto.Protocol.KDF import HKDF
    from Crypto.Util import Counter
except ImportError:
    from Cryptodome import Random
    from Cryptodome.Cipher import AES
    from Cryptodome.Hash import SHA256
    from Cryptodome.Protocol.KDF import HKDF
    from Cryptodome.Util import Counter

cryptorand = Random.new()


def decode_base58_recovery_key(key: str) -> bytes | None:
    key_bytes = base58.b58decode(key.replace(" ", ""))
    if len(key_bytes) != 35 or key_bytes[0] != 0x8B or key_bytes[1] != 1:
        return None
    parity = 0
    for byte in key_bytes[:34]:
        parity ^= byte
    return key_bytes[2:34] if parity == key_bytes[34] else None


def encode_base58_recovery_key(key: bytes) -> str:
    key_bytes = bytearray(35)
    key_bytes[0] = 0x8B
    key_bytes[1] = 1
    key_bytes[2:34] = key
    parity = 0
    for byte in key_bytes:
        parity ^= byte
    key_bytes[34] = parity
    encoded_key = base58.b58encode(key_bytes).decode("utf-8")
    return " ".join(encoded_key[i : i + 4] for i in range(0, len(encoded_key), 4))


def derive_keys(key: bytes, name: str | EventType = "") -> tuple[bytes, bytes]:
    aes_key, hmac_key = HKDF(
        master=key,
        key_len=32,
        salt=b"\x00" * 32,
        hashmod=SHA256,
        num_keys=2,
        context=str(name).encode("utf-8"),
    )
    return aes_key, hmac_key


def prepare_aes(key: bytes, iv: str | bytes) -> AES:
    if isinstance(iv, str):
        iv = unpaddedbase64.decode_base64(iv)
    # initial_value = struct.unpack(">Q", iv[8:])[0]
    # counter = Counter.new(64, prefix=iv[:8], initial_value=initial_value)
    counter = Counter.new(128, initial_value=int.from_bytes(iv, byteorder="big"))
    return AES.new(key=key, mode=AES.MODE_CTR, counter=counter)


def calculate_hash(key: bytes, iv: str | bytes) -> str:
    aes_key, hmac_key = derive_keys(key)
    cipher = prepare_aes(aes_key, iv).decrypt(b"\x00" * 32)
    digest = hmac.digest(hmac_key, cipher, hashlib.sha256)
    return unpaddedbase64.encode_base64(digest)
