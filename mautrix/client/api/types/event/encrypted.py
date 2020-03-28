# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
from attr import dataclass
import attr

from ..util import SerializableAttrs, ExtensibleEnum
from .base import BaseRoomEvent, BaseUnsigned
from .message import RelatesTo


class EncryptionAlgorithm(ExtensibleEnum):
    OLM_V1: 'EncryptionAlgorithm' = "m.olm.v1.curve25519-aes-sha2"
    MEGOLM_V1: 'EncryptionAlgorithm' = "m.megolm.v1.aes-sha2"


@dataclass
class EncryptedEventContent(SerializableAttrs['EncryptedEventContent']):
    """The content of an m.room.encrypted event"""
    algorithm: EncryptionAlgorithm
    ciphertext: str
    sender_key: str
    device_id: str
    session_id: str
    _relates_to: Optional[RelatesTo] = attr.ib(default=None, metadata={"json": "m.relates_to"})

    @property
    def relates_to(self) -> RelatesTo:
        if self._relates_to is None:
            self._relates_to = RelatesTo()
        return self._relates_to

    @relates_to.setter
    def relates_to(self, relates_to: RelatesTo) -> None:
        self._relates_to = relates_to


@dataclass
class EncryptedEvent(BaseRoomEvent, SerializableAttrs['EncryptedEvent']):
    """A m.room.encrypted event"""
    content: EncryptedEventContent
    _unsigned: Optional[BaseUnsigned] = attr.ib(default=None, metadata={"json": "unsigned"})

    @property
    def unsigned(self) -> BaseUnsigned:
        if not self._unsigned:
            self._unsigned = BaseUnsigned()
        return self._unsigned

    @unsigned.setter
    def unsigned(self, value: BaseUnsigned) -> None:
        self._unsigned = value
