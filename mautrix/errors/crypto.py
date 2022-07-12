# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import warnings

from mautrix.types import IdentityKey, SessionID

from .base import MatrixError


class CryptoError(MatrixError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EncryptionError(CryptoError):
    pass


class SessionShareError(CryptoError):
    pass


class DecryptionError(CryptoError):
    @property
    def human_message(self) -> str:
        return "the bridge failed to decrypt the message"


class MatchingSessionDecryptionError(DecryptionError):
    pass


class SessionNotFound(DecryptionError):
    def __init__(self, session_id: SessionID, sender_key: IdentityKey | None = None) -> None:
        super().__init__(
            f"Failed to decrypt megolm event: no session with given ID {session_id} found"
        )
        self.session_id = session_id
        self._sender_key = sender_key

    @property
    def human_message(self) -> str:
        return "the bridge hasn't received the decryption keys"

    @property
    def sender_key(self) -> IdentityKey | None:
        """
        .. deprecated:: 0.17.0
            Matrix v1.3 deprecated the device_id and sender_key fields in megolm events.
        """
        warnings.warn(
            "The sender_key field in Megolm events was deprecated in Matrix 1.3",
            DeprecationWarning,
        )
        return self._sender_key


class DuplicateMessageIndex(DecryptionError):
    def __init__(self) -> None:
        super().__init__("Duplicate message index")


class VerificationError(DecryptionError):
    def __init__(self) -> None:
        super().__init__("Device keys in session and cached device info do not match")


class DecryptedPayloadError(DecryptionError):
    pass


class MismatchingRoomError(DecryptionError):
    def __init__(self) -> None:
        super().__init__("Encrypted megolm event is not intended for this room")


class DeviceValidationError(EncryptionError):
    pass
