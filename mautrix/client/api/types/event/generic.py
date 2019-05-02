# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, NewType

from .....api import JSON
from ..util import deserializer, Obj
from .base import EventType
from .redaction import RedactionEvent
from .message import MessageEvent, MessageEventContent
from .state import StateEvent, StateEventContent
from .account_data import AccountDataEvent, AccountDataEventContent
from .ephemeral import (ReceiptEvent, PresenceEvent, TypingEvent, ReceiptEventContent,
                        TypingEventContent)

Event = NewType("Event", Union[MessageEvent, RedactionEvent, StateEvent, ReceiptEvent,
                               PresenceEvent, TypingEvent, Obj])

EventContent = Union[MessageEventContent, StateEventContent, AccountDataEventContent,
                     ReceiptEventContent, TypingEventContent]


@deserializer(Event)
def deserialize_event(data: JSON) -> Event:
    event_type = EventType.find(data.get("type", None))
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
    elif event_type == EventType.RECEIPT:
        return ReceiptEvent.deserialize(data)
    elif event_type == EventType.TYPING:
        return TypingEvent.deserialize(data)
    elif event_type == EventType.PRESENCE:
        return PresenceEvent.deserialize(data)
    else:
        return Obj(**data)


setattr(Event, "deserialize", deserialize_event)
