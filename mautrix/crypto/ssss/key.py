# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
import base64
import hashlib
import hmac

from attr import dataclass
import unpaddedbase64

from mautrix.types import EventType, SerializableAttrs

from .types import Algorithm, EncryptedKeyData, PassphraseAlgorithm
from .util import (
    calculate_hash,
    cryptorand,
    decode_base58_recovery_key,
    derive_keys,
    encode_base58_recovery_key,
    prepare_aes,
)

try:
    from Crypto.Cipher import AES
    from Crypto.Util import Counter
except ImportError:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util import Counter


@dataclass
class PassphraseMetadata(SerializableAttrs):
    algorithm: PassphraseAlgorithm
    iterations: int
    salt: str
    bits: int = 256

    def get_key(self, passphrase: str) -> bytes:
        if self.algorithm != PassphraseAlgorithm.PBKDF2:
            raise ValueError(f"Unsupported passphrase algorithm {self.algorithm}")
        return hashlib.pbkdf2_hmac(
            "sha512",
            passphrase.encode("utf-8"),
            self.salt.encode("utf-8"),
            self.iterations,
            self.bits // 8,
        )


@dataclass
class KeyMetadata(SerializableAttrs):
    algorithm: Algorithm

    iv: str | None = None
    mac: str | None = None

    name: str | None = None
    passphrase: Optional[PassphraseMetadata] = None

    def verify_passphrase(self, key_id: str, phrase: str) -> "Key":
        if not self.passphrase:
            raise ValueError("Passphrase not set on this key")
        return self.verify_raw_key(key_id, self.passphrase.get_key(phrase))

    def verify_recovery_key(self, key_id: str, recovery_key: str) -> "Key":
        decoded_key = decode_base58_recovery_key(recovery_key)
        if not decoded_key:
            raise ValueError("Invalid recovery key syntax")
        return self.verify_raw_key(key_id, decoded_key)

    def verify_raw_key(self, key_id: str, key: bytes) -> "Key":
        if self.mac.rstrip("=") != calculate_hash(key, self.iv):
            raise ValueError("Key MAC does not match")
        return Key(id=key_id, key=key, metadata=self)


@dataclass
class Key:
    id: str
    key: bytes
    metadata: KeyMetadata

    @classmethod
    def generate(cls, passphrase: str | None = None) -> "Key":
        passphrase_meta = (
            PassphraseMetadata(
                algorithm=PassphraseAlgorithm.PBKDF2,
                iterations=500_000,
                salt=base64.b64encode(cryptorand.read(24)).decode("utf-8"),
                bits=256,
            )
            if passphrase
            else None
        )
        key = passphrase_meta.get_key(passphrase) if passphrase else cryptorand.read(32)
        iv = unpaddedbase64.encode_base64(cryptorand.read(16))
        metadata = KeyMetadata(
            algorithm=Algorithm.AES_HMAC_SHA2,
            passphrase=passphrase_meta,
            mac=calculate_hash(key, iv),
            iv=iv,
        )
        key_id = unpaddedbase64.encode_base64(cryptorand.read(24))
        return cls(key=key, id=key_id, metadata=metadata)

    @property
    def recovery_key(self) -> str:
        return encode_base58_recovery_key(self.key)

    def encrypt(self, event_type: str | EventType, data: str | bytes) -> EncryptedKeyData:
        if isinstance(data, str):
            data = data.encode("utf-8")
        data = base64.b64encode(data).rstrip(b"=")

        aes_key, hmac_key = derive_keys(self.key, event_type)
        iv = bytearray(cryptorand.read(16))
        iv[8] &= 0x7F
        ciphertext = prepare_aes(aes_key, iv).encrypt(data)
        digest = hmac.digest(hmac_key, ciphertext, hashlib.sha256)
        return EncryptedKeyData(
            ciphertext=unpaddedbase64.encode_base64(ciphertext),
            iv=unpaddedbase64.encode_base64(iv),
            mac=unpaddedbase64.encode_base64(digest),
        )

    def decrypt(self, event_type: str | EventType, data: EncryptedKeyData) -> bytes:
        aes_key, hmac_key = derive_keys(self.key, event_type)
        ciphertext = unpaddedbase64.decode_base64(data.ciphertext)
        mac = unpaddedbase64.decode_base64(data.mac)

        expected_mac = hmac.digest(hmac_key, ciphertext, hashlib.sha256)
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("Invalid MAC")

        plaintext = prepare_aes(aes_key, data.iv).decrypt(ciphertext)
        return unpaddedbase64.decode_base64(plaintext.decode("utf-8"))
