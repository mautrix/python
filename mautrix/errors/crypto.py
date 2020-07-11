# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
class CryptoError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EncryptionError(CryptoError):
    pass


class SessionShareError(CryptoError):
    pass


class DecryptionError(CryptoError):
    pass


class MatchingSessionDecryptionError(DecryptionError):
    pass


class DeviceValidationError(EncryptionError):
    pass
