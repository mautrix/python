# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, Optional, cast
from datetime import datetime

import olm

from mautrix.types import (
    DeviceID,
    EncryptionAlgorithm,
    EncryptionKeyAlgorithm,
    IdentityKey,
    SigningKey,
    UserID,
)

from . import base
from .sessions import Session


class OlmAccount(olm.Account):
    shared: bool
    _signing_key: Optional[SigningKey]
    _identity_key: Optional[IdentityKey]

    def __init__(self) -> None:
        super().__init__()
        self.shared = False
        self._signing_key = None
        self._identity_key = None

    @property
    def signing_key(self) -> SigningKey:
        if self._signing_key is None:
            self._signing_key = SigningKey(self.identity_keys["ed25519"])
        return self._signing_key

    @property
    def identity_key(self) -> IdentityKey:
        if self._identity_key is None:
            self._identity_key = IdentityKey(self.identity_keys["curve25519"])
        return self._identity_key

    @property
    def fingerprint(self) -> str:
        """
        Fingerprint is the base64-encoded signing key of this account, with spaces every 4
        characters. This is what is used for manual device verification.
        """
        key = self.signing_key
        return " ".join([key[i : i + 4] for i in range(0, len(key), 4)])

    @classmethod
    def from_pickle(cls, pickle: bytes, passphrase: str, shared: bool) -> "OlmAccount":
        account = cast(OlmAccount, super().from_pickle(pickle, passphrase))
        account.shared = shared
        account._signing_key = None
        account._identity_key = None
        return account

    def new_inbound_session(self, sender_key: IdentityKey, ciphertext: str) -> Session:
        session = olm.InboundSession(self, olm.OlmPreKeyMessage(ciphertext), sender_key)
        self.remove_one_time_keys(session)
        return Session.from_pickle(
            session.pickle("roundtrip"), passphrase="roundtrip", creation_time=datetime.now()
        )

    def new_outbound_session(self, target_key: IdentityKey, one_time_key: IdentityKey) -> Session:
        session = olm.OutboundSession(self, target_key, one_time_key)
        return Session.from_pickle(
            session.pickle("roundtrip"), passphrase="roundtrip", creation_time=datetime.now()
        )

    def get_device_keys(self, user_id: UserID, device_id: DeviceID) -> Dict[str, Any]:
        device_keys = {
            "user_id": user_id,
            "device_id": device_id,
            "algorithms": [EncryptionAlgorithm.OLM_V1.value, EncryptionAlgorithm.MEGOLM_V1.value],
            "keys": {
                f"{algorithm}:{device_id}": key for algorithm, key in self.identity_keys.items()
            },
        }
        signature = self.sign(base.canonical_json(device_keys))
        device_keys["signatures"] = {
            user_id: {f"{EncryptionKeyAlgorithm.ED25519}:{device_id}": signature}
        }
        return device_keys

    def get_one_time_keys(
        self, user_id: UserID, device_id: DeviceID, current_otk_count: int
    ) -> Dict[str, Any]:
        new_count = self.max_one_time_keys // 2 - current_otk_count
        if new_count > 0:
            self.generate_one_time_keys(new_count)
        keys = {}
        for key_id, key in self.one_time_keys.get("curve25519", {}).items():
            signature = self.sign(base.canonical_json({"key": key}))
            keys[f"{EncryptionKeyAlgorithm.SIGNED_CURVE25519}:{key_id}"] = {
                "key": key,
                "signatures": {
                    user_id: {f"{EncryptionKeyAlgorithm.ED25519}:{device_id}": signature}
                },
            }
        self.mark_keys_as_published()
        return keys
