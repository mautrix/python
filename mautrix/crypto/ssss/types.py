# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import TYPE_CHECKING

from attr import dataclass

from mautrix.types import EventType, SerializableAttrs, SerializableEnum
from mautrix.types.event.account_data import account_data_event_content_map

if TYPE_CHECKING:
    from .key import Key


class Algorithm(SerializableEnum):
    AES_HMAC_SHA2 = "m.secret_storage.v1.aes-hmac-sha2"
    CURVE25519_AES_SHA2 = "m.secret_storage.v1.curve25519-aes-sha2"


class PassphraseAlgorithm(SerializableEnum):
    PBKDF2 = "m.pbkdf2"


@dataclass
class EncryptedKeyData(SerializableAttrs):
    ciphertext: str
    iv: str
    mac: str


@dataclass
class EncryptedAccountDataEventContent(SerializableAttrs):
    encrypted: dict[str, EncryptedKeyData]

    def decrypt(self, event_type: str | EventType, key: "Key") -> bytes:
        try:
            encrypted_data = self.encrypted[key.id]
        except KeyError as e:
            raise ValueError(f"Event not encrypted for provided key") from e
        return key.decrypt(event_type, encrypted_data)


for encrypted_account_data_type in (
    EventType.CROSS_SIGNING_MASTER,
    EventType.CROSS_SIGNING_USER_SIGNING,
    EventType.CROSS_SIGNING_SELF_SIGNING,
    EventType.MEGOLM_BACKUP_V1,
):
    account_data_event_content_map[encrypted_account_data_type] = EncryptedAccountDataEventContent
