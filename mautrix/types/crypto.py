# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, List, Optional
from attr import dataclass

from .primitive import UserID, DeviceID, IdentityKey, SigningKey
from .util import SerializableAttrs
from .event.encrypted import EncryptionAlgorithm, EncryptionKeyAlgorithm


@dataclass
class UnsignedDeviceInfo(SerializableAttrs['UnsignedDeviceInfo']):
    device_display_name: Optional[str] = None


@dataclass
class DeviceKeys(SerializableAttrs['DeviceKeys']):
    user_id: UserID
    device_id: DeviceID
    algorithms: List[EncryptionAlgorithm]
    keys: Dict[str, str]
    signatures: Dict[UserID, Dict[str, str]]
    unsigned: UnsignedDeviceInfo = None

    def __attrs_post_init__(self) -> None:
        if self.unsigned is None:
            self.unsigned = UnsignedDeviceInfo()

    @property
    def ed25519(self) -> SigningKey:
        try:
            return self.keys[f"{EncryptionKeyAlgorithm.ED25519}:{self.device_id}"]
        except KeyError:
            return None

    @property
    def curve25519(self) -> IdentityKey:
        try:
            return self.keys[f"{EncryptionKeyAlgorithm.CURVE25519}:{self.device_id}"]
        except KeyError:
            return None


@dataclass
class QueryKeysResponse(SerializableAttrs['QueryKeysResponse']):
    failures: Dict[str, Any]
    device_keys: Dict[UserID, Dict[DeviceID, DeviceKeys]]


@dataclass
class ClaimKeysResponse(SerializableAttrs['ClaimKeysResponse']):
    failures: Dict[str, Any]
    one_time_keys: Dict[UserID, Dict[DeviceID, Dict[str, Any]]]
