from typing import Dict, Union
from attr import dataclass
import attr

from .....api import JSON
from ..util import SerializableAttrs, Obj, deserializer
from .base import EventType, BaseEvent


@dataclass
class RoomTagInfo(SerializableAttrs['RoomTagInfo']):
    order: int = None


@dataclass
class RoomTagAccountDataEventContent(SerializableAttrs['RoomTagAccountDataEventContent']):
    tags: Dict[str, RoomTagInfo] = attr.ib(default=None, metadata={"json": "tags"})


AccountDataEventContent = Union[RoomTagAccountDataEventContent, Obj]
account_data_event_content_map = {
    EventType.TAG: RoomTagAccountDataEventContent
}

# TODO remaining account data event types


@dataclass
class AccountDataEvent(BaseEvent, SerializableAttrs['AccountDataEvent']):
    content: AccountDataEventContent

    @classmethod
    @deserializer(AccountDataEventContent)
    def deserialize_content(cls, data: JSON) -> AccountDataEventContent:
        evt_type = data.pop("__mautrix_event_type", None)
        content_type = account_data_event_content_map.get(evt_type, None)
        if not content_type:
            return Obj(**data)
        return content_type.deserialize(data)
