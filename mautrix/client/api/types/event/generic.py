from typing import Union, NewType

from .....api import JSON
from ..util import deserializer, Obj
from .base import EventType
from .message import MessageEvent, StickerEvent, RedactionEvent
from .state import StateEvent
from .account_data import AccountDataEvent

Event = NewType("Event", Union[MessageEvent, StickerEvent, RedactionEvent, StateEvent, Obj])


@deserializer(Event)
def deserialize_event(data: JSON) -> Event:
    try:
        event_type = EventType(data.get("type", None))
    except ValueError:
        return Obj(**data)
    if event_type == EventType.ROOM_MESSAGE:
        return MessageEvent.deserialize(data)
    elif event_type == EventType.STICKER:
        return StickerEvent.deserialize(data)
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
