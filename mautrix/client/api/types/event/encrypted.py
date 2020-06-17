# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, Union
from enum import IntEnum
from attr import dataclass
import attr

from mautrix.api import JSON
from ..util import SerializableAttrs, Serializable, ExtensibleEnum, Obj, deserializer
from .base import BaseRoomEvent, BaseUnsigned
from .message import RelatesTo


class EncryptionAlgorithm(ExtensibleEnum):
    OLM_V1: 'EncryptionAlgorithm' = "m.olm.v1.curve25519-aes-sha2"
    MEGOLM_V1: 'EncryptionAlgorithm' = "m.megolm.v1.aes-sha2"


class OlmMsgType(Serializable, IntEnum):
    PREKEY = 0
    MESSAGE = 1

    def serialize(self) -> JSON:
        return self.value

    @classmethod
    def deserialize(cls, raw: JSON) -> 'OlmMsgType':
        return cls(raw)


@dataclass
class OlmCiphertext(SerializableAttrs['OlmCiphertext']):
    body: str
    type: OlmMsgType


class BaseEncryptedEventContent:
    _relates_to: Optional[RelatesTo]

    @property
    def relates_to(self) -> RelatesTo:
        if self._relates_to is None:
            self._relates_to = RelatesTo()
        return self._relates_to

    @relates_to.setter
    def relates_to(self, relates_to: RelatesTo) -> None:
        self._relates_to = relates_to


@dataclass
class EncryptedOlmEventContent(SerializableAttrs['EncryptedOlmEventContent'],
                               BaseEncryptedEventContent):
    ciphertext: Dict[str, OlmCiphertext]
    sender_key: str
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.OLM_V1


@dataclass
class EncryptedMegolmEventContent(SerializableAttrs['EncryptedMegolmEventContent'],
                                  BaseEncryptedEventContent):
    """The content of an m.room.encrypted event"""
    ciphertext: str
    sender_key: str
    device_id: str
    session_id: str
    _relates_to: Optional[RelatesTo] = attr.ib(default=None, metadata={"json": "m.relates_to"})
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.MEGOLM_V1


EncryptedEventContent = Union[EncryptedOlmEventContent, EncryptedMegolmEventContent]


@deserializer(EncryptedEventContent)
def deserialize_encrypted(data: JSON) -> Union[EncryptedEventContent, Obj]:
    alg = data.get("algorithm", None)
    if alg == EncryptionAlgorithm.MEGOLM_V1.value:
        return EncryptedMegolmEventContent.deserialize(data)
    elif alg == EncryptionAlgorithm.OLM_V1.value:
        return EncryptedOlmEventContent.deserialize(data)
    return Obj(**data)


setattr(EncryptedEventContent, "deserialize", deserialize_encrypted)


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
