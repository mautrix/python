# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Union
from attr import dataclass
import attr

from mautrix.api import JSON

from ..util import SerializableAttrs, Obj, deserializer
from .encrypted import EncryptionAlgorithm, OlmCiphertext
from .base import EventType, BaseEvent


@dataclass
class EncryptedToDeviceEventContent(SerializableAttrs['EncryptedToDeviceEventContent']):
    ciphertext: Dict[str, OlmCiphertext]
    sender_key: str
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.OLM_V1


ToDeviceEventContent = Union[Obj, EncryptedToDeviceEventContent]
to_device_event_content_map = {
    EventType.TO_DEVICE_ENCRYPTED: EncryptedToDeviceEventContent
}


# TODO remaining account data event types


@dataclass
class ToDeviceEvent(BaseEvent, SerializableAttrs['ToDeviceEvent']):
    content: ToDeviceEventContent

    @classmethod
    def deserialize(cls, data: JSON) -> 'ToDeviceEvent':
        try:
            evt_type = EventType.find(data.get("type"), t_class=EventType.Class.TO_DEVICE)
            data.get("content", {})["__mautrix_event_type"] = evt_type
        except ValueError:
            return Obj(**data)
        return super().deserialize(data)

    @staticmethod
    @deserializer(ToDeviceEventContent)
    def deserialize_content(data: JSON) -> ToDeviceEventContent:
        evt_type = data.pop("__mautrix_event_type", None)
        content_type = to_device_event_content_map.get(evt_type, None)
        if not content_type:
            return Obj(**data)
        return content_type.deserialize(data)
