# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, List, NamedTuple, Optional
from enum import IntEnum

from attr import dataclass

from .event import EncryptionAlgorithm, EncryptionKeyAlgorithm, KeyID, ToDeviceEvent
from .primitive import DeviceID, IdentityKey, Signature, SigningKey, UserID
from .util import ExtensibleEnum, SerializableAttrs, field


@dataclass
class UnsignedDeviceInfo(SerializableAttrs):
    device_display_name: Optional[str] = None


@dataclass
class DeviceKeys(SerializableAttrs):
    user_id: UserID
    device_id: DeviceID
    algorithms: List[EncryptionAlgorithm]
    keys: Dict[KeyID, str]
    signatures: Dict[UserID, Dict[KeyID, Signature]]
    unsigned: UnsignedDeviceInfo = None

    def __attrs_post_init__(self) -> None:
        if self.unsigned is None:
            self.unsigned = UnsignedDeviceInfo()

    @property
    def ed25519(self) -> Optional[SigningKey]:
        try:
            return SigningKey(self.keys[KeyID(EncryptionKeyAlgorithm.ED25519, self.device_id)])
        except KeyError:
            return None

    @property
    def curve25519(self) -> Optional[IdentityKey]:
        try:
            return IdentityKey(self.keys[KeyID(EncryptionKeyAlgorithm.CURVE25519, self.device_id)])
        except KeyError:
            return None


class CrossSigningUsage(ExtensibleEnum):
    MASTER = "master"
    SELF = "self_signing"
    USER = "user_signing"


@dataclass
class CrossSigningKeys(SerializableAttrs):
    user_id: UserID
    usage: List[CrossSigningUsage]
    keys: Dict[str, SigningKey]
    signatures: Dict[UserID, Dict[KeyID, Signature]] = field(factory=lambda: {})

    @property
    def first_key(self) -> Optional[SigningKey]:
        try:
            return next(iter(self.keys.values()))
        except StopIteration:
            return None


@dataclass
class QueryKeysResponse(SerializableAttrs):
    failures: Dict[str, Any]
    device_keys: Dict[UserID, Dict[DeviceID, DeviceKeys]]
    master_keys: Dict[UserID, CrossSigningKeys]
    self_signing_keys: Dict[UserID, CrossSigningKeys]
    user_signing_keys: Dict[UserID, CrossSigningKeys]


@dataclass
class ClaimKeysResponse(SerializableAttrs):
    failures: Dict[str, Any]
    one_time_keys: Dict[UserID, Dict[DeviceID, Dict[KeyID, Any]]]


class TrustState(IntEnum):
    BLACKLISTED = -100
    UNSET = 0
    UNKNOWN_DEVICE = 10
    FORWARDED = 20
    CROSS_SIGNED_UNTRUSTED = 50
    CROSS_SIGNED_TOFU = 100
    CROSS_SIGNED_TRUSTED = 200
    VERIFIED = 300


@dataclass
class DeviceIdentity:
    user_id: UserID
    device_id: DeviceID
    identity_key: IdentityKey
    signing_key: SigningKey

    trust: TrustState
    deleted: bool
    name: str


@dataclass
class OlmEventKeys(SerializableAttrs):
    ed25519: SigningKey


@dataclass
class DecryptedOlmEvent(ToDeviceEvent, SerializableAttrs):
    keys: OlmEventKeys
    recipient: UserID
    recipient_keys: OlmEventKeys
    sender_device: Optional[DeviceID] = None
    sender_key: IdentityKey = field(hidden=True, default=None)


class TOFUSigningKey(NamedTuple):
    """
    A tuple representing a single cross-signing key. The first value is the current key, and the
    second value is the first seen key. If the values don't match, it means the key is not valid
    for trust-on-first-use.
    """

    key: SigningKey
    first: SigningKey


class CrossSigner(NamedTuple):
    """
    A tuple containing a user ID and a signing key they own.

    The key can either be a device-owned signing key, or one of the user's cross-signing keys.
    """

    user_id: UserID
    key: SigningKey
