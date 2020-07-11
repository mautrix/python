# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, Optional
from attr import dataclass

from ..util import SerializableAttrs, Obj, deserializer, ExtensibleEnum
from ..primitive import JSON, UserID, RoomID, SessionID, IdentityKey
from .encrypted import EncryptionAlgorithm, EncryptedOlmEventContent
from .base import EventType, BaseEvent


class RoomKeyWithheldCode(ExtensibleEnum):
    BLACKLISTED: 'RoomKeyWithheldCode' = "m.blacklisted"
    UNVERIFIED: 'RoomKeyWithheldCode' = "m.unverified"
    UNAUTHORIZED: 'RoomKeyWithheldCode' = "m.unauthorized"
    UNAVAILABLE: 'RoomKeyWithheldCode' = "m.unavailable"
    NO_OLM_SESSION: 'RoomKeyWithheldCode' = "m.no_olm"


@dataclass
class RoomKeyWithheldEventContent(SerializableAttrs['RoomKeyWithheldEventContent']):
    algorithm: EncryptionAlgorithm
    sender_key: IdentityKey
    code: RoomKeyWithheldCode
    reason: Optional[str] = None
    room_id: Optional[RoomID] = None
    session_id: Optional[SessionID] = None


@dataclass
class RoomKeyEventContent(SerializableAttrs['RoomKeyEventContent']):
    algorithm: EncryptionAlgorithm
    room_id: RoomID
    session_id: SessionID
    session_key: str


ToDeviceEventContent = Union[Obj, EncryptedOlmEventContent, RoomKeyWithheldEventContent,
                             RoomKeyEventContent]
to_device_event_content_map = {
    EventType.TO_DEVICE_ENCRYPTED: EncryptedOlmEventContent,
    EventType.ROOM_KEY_WITHHELD: RoomKeyWithheldEventContent,
    EventType.ROOM_KEY: RoomKeyEventContent,
}


# TODO remaining account data event types


@dataclass
class ToDeviceEvent(BaseEvent, SerializableAttrs['ToDeviceEvent']):
    sender: UserID
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
