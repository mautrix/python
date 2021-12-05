# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
from enum import IntEnum

from attr import dataclass
import attr

from mautrix.types import (
    DeviceID,
    IdentityKey,
    SerializableAttrs,
    SigningKey,
    ToDeviceEvent,
    UserID,
)


class TrustState(IntEnum):
    UNSET = 0
    VERIFIED = 1
    BLACKLISTED = 2
    IGNORED = 3


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
    sender_key: IdentityKey = attr.ib(metadata={"hidden": True}, default=None)
