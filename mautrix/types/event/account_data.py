# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Union
from attr import dataclass
import attr

from ..primitive import JSON, RoomID, UserID
from ..util import SerializableAttrs, Obj, deserializer
from .base import EventType, BaseEvent


@dataclass
class RoomTagInfo(SerializableAttrs['RoomTagInfo']):
    order: int = None


@dataclass
class RoomTagAccountDataEventContent(SerializableAttrs['RoomTagAccountDataEventContent']):
    tags: Dict[str, RoomTagInfo] = attr.ib(default=None, metadata={"json": "tags"})


DirectAccountDataEventContent = Dict[UserID, List[RoomID]]


AccountDataEventContent = Union[RoomTagAccountDataEventContent, DirectAccountDataEventContent, Obj]
account_data_event_content_map = {
    EventType.TAG: RoomTagAccountDataEventContent,
}


# TODO remaining account data event types


@dataclass
class AccountDataEvent(BaseEvent, SerializableAttrs['AccountDataEvent']):
    content: AccountDataEventContent

    @classmethod
    def deserialize(cls, data: JSON) -> 'AccountDataEvent':
        try:
            data.get("content", {})["__mautrix_event_type"] = EventType.find(data.get("type"))
        except ValueError:
            return Obj(**data)
        return super().deserialize(data)

    @staticmethod
    @deserializer(AccountDataEventContent)
    def deserialize_content(data: JSON) -> AccountDataEventContent:
        evt_type = data.pop("__mautrix_event_type", None)
        content_type = account_data_event_content_map.get(evt_type, None)
        if not content_type:
            return Obj(**data)
        return content_type.deserialize(data)
