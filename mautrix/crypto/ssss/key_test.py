# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest

from ...types.event.type import EventType
from .key import Key, KeyMetadata
from .types import EncryptedAccountDataEventContent

KEY1_CROSS_SIGNING_MASTER_KEY = """{
  "encrypted": {
    "gEJqbfSEMnP5JXXcukpXEX1l0aI3MDs0": {
      "iv": "BpKP9nQJTE9jrsAssoxPqQ==",
      "ciphertext": "fNRiiiidezjerTgV+G6pUtmeF3izzj5re/mVvY0hO2kM6kYGrxLuIu2ej80=",
      "mac": "/gWGDGMyOLmbJp+aoSLh5JxCs0AdS6nAhjzpe+9G2Q0="
    }
  }
}"""

KEY1_CROSS_SIGNING_MASTER_KEY_DECRYPTED = bytes(
    [
        0x68,
        0xF9,
        0x7F,
        0xD1,
        0x92,
        0x2E,
        0xEC,
        0xF6,
        0xB8,
        0x2B,
        0xB8,
        0x90,
        0xD2,
        0x4D,
        0x06,
        0x52,
        0x98,
        0x4E,
        0x7A,
        0x1D,
        0x70,
        0x3B,
        0x9E,
        0x86,
        0x7B,
        0x7E,
        0xBA,
        0xF7,
        0xFE,
        0xB9,
        0x5B,
        0x6F,
    ]
)

KEY1_META = """{
  "algorithm": "m.secret_storage.v1.aes-hmac-sha2",
  "passphrase": {
    "algorithm": "m.pbkdf2",
    "iterations": 500000,
    "salt": "y863BOoqOadgDp8S3FtHXikDJEalsQ7d"
  },
  "iv": "xxkTK0L4UzxgAFkQ6XPwsw",
  "mac": "MEhooO0ZhFJNxUhvRMSxBnJfL20wkLgle3ocY0ee/eA"
}"""
KEY1_ID = "gEJqbfSEMnP5JXXcukpXEX1l0aI3MDs0"
KEY1_RECOVERY_KEY = "EsTE s92N EtaX s2h6 VQYF 9Kao tHYL mkyL GKMh isZb KJ4E tvoC"
KEY1_PASSPHRASE = "correct horse battery staple"

KEY2_META = """{
  "algorithm": "m.secret_storage.v1.aes-hmac-sha2",
  "iv": "O0BOvTqiIAYjC+RMcyHfWw==",
  "mac": "7k6OruQlWg0UmQjxGZ0ad4Q6DdwkgnoI7G6X3IjBYtI="
}"""
KEY2_ID = "NVe5vK6lZS9gEMQLJw0yqkzmE5Mr7dLv"
KEY2_RECOVERY_KEY = "EsUC xSxt XJgQ dz19 8WBZ rHdE GZo7 ybsn EFmG Y5HY MDAG GNWe"

KEY2_META_BROKEN_IV = """{
  "algorithm": "m.secret_storage.v1.aes-hmac-sha2",
  "iv": "O0BOvTqiIAYjC+RMcyHfWwMeowMeowMeow",
  "mac": "7k6OruQlWg0UmQjxGZ0ad4Q6DdwkgnoI7G6X3IjBYtI="
}"""

KEY2_META_BROKEN_MAC = """{
  "algorithm": "m.secret_storage.v1.aes-hmac-sha2",
  "iv": "O0BOvTqiIAYjC+RMcyHfWw==",
  "mac": "7k6OruQlWg0UmQjxGZ0ad4Q6DdwkgnoI7G6X3IjBYtIMeowMeowMeow"
}"""


def get_key_meta(meta: str) -> KeyMetadata:
    return KeyMetadata.parse_json(meta)


def get_key1() -> Key:
    return get_key_meta(KEY1_META).verify_recovery_key(KEY1_ID, KEY1_RECOVERY_KEY)


def get_key2() -> Key:
    return get_key_meta(KEY2_META).verify_recovery_key(KEY2_ID, KEY2_RECOVERY_KEY)


def get_encrypted_master_key() -> EncryptedAccountDataEventContent:
    return EncryptedAccountDataEventContent.parse_json(KEY1_CROSS_SIGNING_MASTER_KEY)


def test_decrypt_success() -> None:
    key = get_key1()
    emk = get_encrypted_master_key()
    assert (
        emk.decrypt(EventType.CROSS_SIGNING_MASTER, key) == KEY1_CROSS_SIGNING_MASTER_KEY_DECRYPTED
    )


def test_decrypt_fail_wrong_key() -> None:
    key = get_key2()
    emk = get_encrypted_master_key()
    with pytest.raises(ValueError):
        emk.decrypt(EventType.CROSS_SIGNING_MASTER, key)


def test_decrypt_fail_fake_key() -> None:
    key = get_key2()
    key.id = KEY1_ID
    emk = get_encrypted_master_key()
    with pytest.raises(ValueError):
        emk.decrypt(EventType.CROSS_SIGNING_MASTER, key)


def test_decrypt_fail_wrong_type() -> None:
    key = get_key1()
    emk = get_encrypted_master_key()
    with pytest.raises(ValueError):
        emk.decrypt(EventType.CROSS_SIGNING_SELF_SIGNING, key)


def test_encrypt_roundtrip() -> None:
    key = get_key1()
    data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
    ciphertext = key.encrypt("net.maunium.data", data)
    plaintext = key.decrypt("net.maunium.data", ciphertext)
    assert plaintext == data


def test_verify_recovery_key_correct() -> None:
    meta = get_key_meta(KEY1_META)
    key = meta.verify_recovery_key(KEY1_ID, KEY1_RECOVERY_KEY)
    assert key.recovery_key == KEY1_RECOVERY_KEY


def test_verify_recovery_key_correct2() -> None:
    meta = get_key_meta(KEY2_META)
    key = meta.verify_recovery_key(KEY2_ID, KEY2_RECOVERY_KEY)
    assert key.recovery_key == KEY2_RECOVERY_KEY


def test_verify_recovery_key_invalid() -> None:
    meta = get_key_meta(KEY1_META)
    with pytest.raises(ValueError):
        meta.verify_recovery_key(KEY1_ID, "foo")


def test_verify_recovery_key_incorrect() -> None:
    meta = get_key_meta(KEY1_META)
    with pytest.raises(ValueError):
        meta.verify_recovery_key(KEY2_ID, KEY2_RECOVERY_KEY)


def test_verify_recovery_key_broken_iv() -> None:
    meta = get_key_meta(KEY2_META_BROKEN_IV)
    with pytest.raises(ValueError):
        meta.verify_recovery_key(KEY2_ID, KEY2_RECOVERY_KEY)


def test_verify_recovery_key_broken_mac() -> None:
    meta = get_key_meta(KEY2_META_BROKEN_MAC)
    with pytest.raises(ValueError):
        meta.verify_recovery_key(KEY2_ID, KEY2_RECOVERY_KEY)


def test_verify_passphrase_correct() -> None:
    meta = get_key_meta(KEY1_META)
    key = meta.verify_passphrase(KEY1_ID, KEY1_PASSPHRASE)
    assert key.recovery_key == KEY1_RECOVERY_KEY


def test_verify_passphrase_incorrect() -> None:
    meta = get_key_meta(KEY1_META)
    with pytest.raises(ValueError):
        meta.verify_passphrase(KEY1_ID, "incorrect horse battery staple")


def test_verify_passphrase_notset() -> None:
    meta = get_key_meta(KEY2_META)
    with pytest.raises(ValueError):
        meta.verify_passphrase(KEY2_ID, "hmm")
