# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, List, Optional
from attr import dataclass
import attr

from .primitive import UserID, DeviceID
from .util import SerializableAttrs
from .event.encrypted import EncryptionKeyAlgorithm


@dataclass
class UnsignedDeviceInfo(SerializableAttrs['UnsignedDeviceInfo']):
    device_display_name: Optional[str] = None


@dataclass
class DeviceKeys(SerializableAttrs['DeviceKeys']):
    user_id: UserID
    device_id: DeviceID
    algorithms: List[EncryptionKeyAlgorithm]
    signatures: Dict[UserID, Dict[str, str]]
    unsigned: UnsignedDeviceInfo = attr.ib(factory=UnsignedDeviceInfo)


@dataclass
class QueryKeysResponse(SerializableAttrs['QueryKeysResponse']):
    failures: Dict[str, Any]
    device_keys: Dict[UserID, Dict[DeviceID, DeviceKeys]]
    one_time_keys: Dict[UserID, Dict[DeviceID, Dict[str, Any]]]


@dataclass
class ClaimKeysResponse(SerializableAttrs['ClaimKeysResponse']):
    failures: Dict[str, Any]
    one_time_keys: Dict[UserID, Dict[DeviceID, Dict[str, Any]]]
