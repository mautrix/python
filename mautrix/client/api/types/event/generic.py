from typing import Union, NewType

from .....api import JSON
from ..util import deserializer, Obj
from .base import EventType
from .redaction import RedactionEvent
from .message import MessageEvent, MessageEventContent
from .state import StateEvent, StateEventContent
from .account_data import AccountDataEvent, AccountDataEventContent

Event = NewType("Event", Union[MessageEvent, RedactionEvent, StateEvent, Obj])
EventContent = Union[MessageEventContent, StateEventContent, AccountDataEventContent]


@deserializer(Event)
def deserialize_event(data: JSON) -> Event:
    try:
        event_type = EventType(data.get("type", None))
    except ValueError:
        return Obj(**data)
    if event_type == EventType.ROOM_MESSAGE:
        return MessageEvent.deserialize(data)
    elif event_type == EventType.STICKER:
        data.get("content", {})["msgtype"] = "m.sticker"
        return MessageEvent.deserialize(data)
    elif event_type == EventType.ROOM_REDACTION:
        return RedactionEvent.deserialize(data)
    elif event_type.is_state:
        return StateEvent.deserialize(data)
    elif event_type.is_account_data:
        return AccountDataEvent.deserialize(data)
    elif event_type.is_ephemeral:
        # TODO implement
        return Obj(**data)
    else:
        return Obj(**data)


setattr(Event, "deserialize", deserialize_event)
