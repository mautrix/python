# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import TYPE_CHECKING

from .base import MatrixError

if TYPE_CHECKING:
    from mautrix.types import SessionID, IdentityKey


class CryptoError(MatrixError):
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


class SessionNotFound(DecryptionError):
    def __init__(self, session_id: 'SessionID', sender_key: 'IdentityKey') -> None:
        super().__init__("Failed to decrypt megolm event: "
                         f"no session with given ID {session_id} found")
        self.session_id = session_id
        self.sender_key = sender_key


class DuplicateMessageIndex(DecryptionError):
    def __init__(self) -> None:
        super().__init__("Duplicate message index")


class VerificationError(DecryptionError):
    def __init__(self) -> None:
        super().__init__("Device keys in event and verified device info do not match")


class DecryptedPayloadError(DecryptionError):
    pass


class MismatchingRoomError(DecryptionError):
    def __init__(self) -> None:
        super().__init__("Encrypted megolm event is not intended for this room")


class DeviceValidationError(EncryptionError):
    pass
