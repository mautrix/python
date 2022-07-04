# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, NewType, Optional, Union
from enum import IntEnum
import warnings

from attr import dataclass

from ..primitive import JSON, DeviceID, IdentityKey, SessionID
from ..util import ExtensibleEnum, Obj, Serializable, SerializableAttrs, deserializer, field
from .base import BaseRoomEvent, BaseUnsigned
from .message import RelatesTo


class EncryptionAlgorithm(ExtensibleEnum):
    OLM_V1: "EncryptionAlgorithm" = "m.olm.v1.curve25519-aes-sha2"
    MEGOLM_V1: "EncryptionAlgorithm" = "m.megolm.v1.aes-sha2"


class EncryptionKeyAlgorithm(ExtensibleEnum):
    CURVE25519: "EncryptionKeyAlgorithm" = "curve25519"
    ED25519: "EncryptionKeyAlgorithm" = "ed25519"
    SIGNED_CURVE25519: "EncryptionKeyAlgorithm" = "signed_curve25519"


@dataclass(frozen=True)
class KeyID(Serializable):
    algorithm: EncryptionKeyAlgorithm
    key_id: str

    def serialize(self) -> JSON:
        return str(self)

    @classmethod
    def deserialize(cls, raw: JSON) -> "KeyID":
        assert isinstance(raw, str), "key IDs must be strings"
        alg, key_id = raw.split(":", 1)
        return cls(EncryptionKeyAlgorithm(alg), key_id)

    def __str__(self) -> str:
        return f"{self.algorithm.value}:{self.key_id}"


class OlmMsgType(Serializable, IntEnum):
    PREKEY = 0
    MESSAGE = 1

    def serialize(self) -> JSON:
        return self.value

    @classmethod
    def deserialize(cls, raw: JSON) -> "OlmMsgType":
        return cls(raw)


@dataclass
class OlmCiphertext(SerializableAttrs):
    body: str
    type: OlmMsgType


@dataclass
class EncryptedOlmEventContent(SerializableAttrs):
    ciphertext: Dict[str, OlmCiphertext]
    sender_key: IdentityKey
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.OLM_V1


@dataclass
class EncryptedMegolmEventContent(SerializableAttrs):
    """The content of an m.room.encrypted event"""

    ciphertext: str
    session_id: SessionID
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.MEGOLM_V1

    _sender_key: Optional[IdentityKey] = field(default=None, json="sender_key")
    _device_id: Optional[DeviceID] = field(default=None, json="device_id")
    _relates_to: Optional[RelatesTo] = field(default=None, json="m.relates_to")

    @property
    def sender_key(self) -> Optional[IdentityKey]:
        """
        .. deprecated:: 0.17.0
            Matrix v1.3 deprecated the device_id and sender_key fields in megolm events.
        """
        warnings.warn(
            "The sender_key field in Megolm events was deprecated in Matrix 1.3",
            DeprecationWarning,
        )
        return self._sender_key

    @property
    def device_id(self) -> Optional[DeviceID]:
        """
        .. deprecated:: 0.17.0
            Matrix v1.3 deprecated the device_id and sender_key fields in megolm events.
        """
        warnings.warn(
            "The sender_key field in Megolm events was deprecated in Matrix 1.3",
            DeprecationWarning,
        )
        return self._device_id

    @property
    def relates_to(self) -> RelatesTo:
        if self._relates_to is None:
            self._relates_to = RelatesTo()
        return self._relates_to

    @relates_to.setter
    def relates_to(self, relates_to: RelatesTo) -> None:
        self._relates_to = relates_to


EncryptedEventContent = NewType(
    "EncryptedEventContent", Union[EncryptedOlmEventContent, EncryptedMegolmEventContent]
)


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
class EncryptedEvent(BaseRoomEvent, SerializableAttrs):
    """A m.room.encrypted event"""

    content: EncryptedEventContent
    _unsigned: Optional[BaseUnsigned] = field(default=None, json="unsigned")

    @property
    def unsigned(self) -> BaseUnsigned:
        if not self._unsigned:
            self._unsigned = BaseUnsigned()
        return self._unsigned

    @unsigned.setter
    def unsigned(self, value: BaseUnsigned) -> None:
        self._unsigned = value
