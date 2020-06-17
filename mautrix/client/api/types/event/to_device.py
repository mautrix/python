# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Union
from attr import dataclass
import attr

from .....api import JSON
from ..util import SerializableAttrs, Obj, deserializer
from .base import EventType, BaseEvent

ToDeviceEventContent = Union[Obj]
to_device_event_content_map = {

}


# TODO remaining account data event types


@dataclass
class ToDeviceEvent(BaseEvent, SerializableAttrs['ToDeviceEvent']):
    content: ToDeviceEventContent

    @classmethod
    def deserialize(cls, data: JSON) -> 'ToDeviceEvent':
        try:
            data.get("content", {})["__mautrix_event_type"] = EventType.find(data.get("type"))
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
