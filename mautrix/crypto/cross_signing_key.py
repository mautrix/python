# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import NamedTuple

import olm

from mautrix.crypto.ssss.util import cryptorand
from mautrix.types import SigningKey


class CrossSigningPublicKeys(NamedTuple):
    master_key: SigningKey
    self_signing_key: SigningKey
    user_signing_key: SigningKey


class CrossSigningPrivateKeys(NamedTuple):
    master_key: olm.PkSigning
    self_signing_key: olm.PkSigning
    user_signing_key: olm.PkSigning

    @property
    def public_keys(self) -> CrossSigningPublicKeys:
        return CrossSigningPublicKeys(
            master_key=self.master_key.public_key,
            self_signing_key=self.self_signing_key.public_key,
            user_signing_key=self.user_signing_key.public_key,
        )


class CrossSigningSeeds(NamedTuple):
    master_key: bytes
    self_signing_key: bytes
    user_signing_key: bytes

    def to_keys(self) -> CrossSigningPrivateKeys:
        return CrossSigningPrivateKeys(
            master_key=olm.PkSigning(self.master_key),
            self_signing_key=olm.PkSigning(self.self_signing_key),
            user_signing_key=olm.PkSigning(self.user_signing_key),
        )

    @classmethod
    def generate(cls) -> "CrossSigningSeeds":
        return cls(
            master_key=cryptorand.read(32),
            self_signing_key=cryptorand.read(32),
            user_signing_key=cryptorand.read(32),
        )
