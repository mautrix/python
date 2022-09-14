# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, NewType, Union

from attr import dataclass

from ..primitive import JSON, EventID, RoomID, UserID
from ..util import ExtensibleEnum, SerializableAttrs, SerializableEnum, deserializer
from .base import BaseEvent, GenericEvent
from .type import EventType


@dataclass
class TypingEventContent(SerializableAttrs):
    user_ids: List[UserID]


@dataclass
class TypingEvent(BaseEvent, SerializableAttrs):
    room_id: RoomID
    content: TypingEventContent


class PresenceState(SerializableEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"


@dataclass
class PresenceEventContent(SerializableAttrs):
    presence: PresenceState
    last_active_ago: int = None
    status_msg: str = None
    currently_active: bool = None


@dataclass
class PresenceEvent(BaseEvent, SerializableAttrs):
    sender: UserID
    content: PresenceEventContent


@dataclass
class SingleReceiptEventContent(SerializableAttrs):
    ts: int


class ReceiptType(ExtensibleEnum):
    READ = "m.read"
    READ_PRIVATE = "m.read.private"


ReceiptEventContent = Dict[EventID, Dict[ReceiptType, Dict[UserID, SingleReceiptEventContent]]]


@dataclass
class ReceiptEvent(BaseEvent, SerializableAttrs):
    room_id: RoomID
    content: ReceiptEventContent


EphemeralEvent = NewType("EphemeralEvent", Union[PresenceEvent, TypingEvent, ReceiptEvent])


@deserializer(EphemeralEvent)
def deserialize_ephemeral_event(data: JSON) -> EphemeralEvent:
    event_type = EventType.find(data.get("type", None))
    if event_type == EventType.RECEIPT:
        evt = ReceiptEvent.deserialize(data)
    elif event_type == EventType.TYPING:
        evt = TypingEvent.deserialize(data)
    elif event_type == EventType.PRESENCE:
        evt = PresenceEvent.deserialize(data)
    else:
        evt = GenericEvent.deserialize(data)
    evt.type = event_type
    return evt


setattr(EphemeralEvent, "deserialize", deserialize_ephemeral_event)
