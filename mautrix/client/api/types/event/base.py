# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict
import json

from attr import dataclass
import attr

from .....api import JSON
from ..primitive import RoomID, UserID, EventID
from ..util import SerializableEnum, Serializable, Obj


class EventType(Serializable):
    """An event type."""
    by_event_type: Dict[str, 'EventType'] = {}

    class Class(SerializableEnum):
        UNKNOWN = "unknown"
        STATE = "state"
        MESSAGE = "message"
        ACCOUNT_DATA = "account_data"
        EPHEMERAL = "ephemeral"

    ROOM_CANONICAL_ALIAS: 'EventType'
    ROOM_ALIASES: 'EventType'
    ROOM_CREATE: 'EventType'
    ROOM_JOIN_RULES: 'EventType'
    ROOM_MEMBER: 'EventType'
    ROOM_POWER_LEVELS: 'EventType'
    ROOM_NAME: 'EventType'
    ROOM_TOPIC: 'EventType'
    ROOM_AVATAR: 'EventType'
    ROOM_PINNED_EVENTS: 'EventType'

    ROOM_REDACTION: 'EventType'
    ROOM_MESSAGE: 'EventType'
    STICKER: 'EventType'

    RECEIPT: 'EventType'
    TYPING: 'EventType'
    PRESENCE: 'EventType'

    DIRECT: 'EventType'
    PUSH_RULES: 'EventType'
    TAG: 'EventType'
    IGNORED_USER_LIST: 'EventType'

    ALL: 'EventType'

    def __init__(self, t: str, t_class: Class = Class.UNKNOWN):
        self.t = t
        self.t_class = t_class
        self.by_event_type[t] = self

    def serialize(self) -> JSON:
        return self.t

    @classmethod
    def deserialize(cls, raw: JSON) -> Any:
        return cls.find(raw)

    @classmethod
    def find(cls, t: str) -> 'EventType':
        try:
            return cls.by_event_type[t]
        except KeyError:
            return EventType(t)

    def json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def parse_json(cls, data: str) -> 'EventType':
        return cls.deserialize(json.loads(data))

    def __str__(self):
        return self.t

    def __repr__(self):
        return f"EventType(\"{self.t}\", EventType.Class.{self.t_class.name})"

    @property
    def is_message(self) -> bool:
        """Whether or not the event is a message event."""
        return self.t_class == EventType.Class.MESSAGE

    @property
    def is_state(self) -> bool:
        """Whether or not the event is a state event."""
        return self.t_class == EventType.Class.STATE

    @property
    def is_ephemeral(self) -> bool:
        """Whether or not the event is ephemeral."""
        return self.t_class == EventType.Class.EPHEMERAL

    @property
    def is_account_data(self) -> bool:
        """Whether or not the event is an account data event."""
        return self.t_class == EventType.Class.ACCOUNT_DATA


_standard_types = {
    EventType.Class.STATE: {
        "m.room.aliases": "ROOM_ALIASES",
        "m.room.canonical_alias": "ROOM_CANONICAL_ALIAS",
        "m.room.create": "ROOM_CREATE",
        "m.room.join_rules": "ROOM_JOIN_RULES",
        "m.room.member": "ROOM_MEMBER",
        "m.room.power_levels": "ROOM_POWER_LEVELS",
        "m.room.name": "ROOM_NAME",
        "m.room.topic": "ROOM_TOPIC",
        "m.room.avatar": "ROOM_AVATAR",
        "m.room.pinned_events": "ROOM_PINNED_EVENTS",
    },
    EventType.Class.MESSAGE: {
        "m.room.redaction": "ROOM_REDACTION",
        "m.room.message": "ROOM_MESSAGE",
        "m.sticker": "STICKER",
    },
    EventType.Class.EPHEMERAL: {
        "m.receipt": "RECEIPT",
        "m.typing": "TYPING",
        "m.presence": "PRESENCE",
    },
    EventType.Class.ACCOUNT_DATA: {
        "m.direct": "DIRECT",
        "m.push_rules": "PUSH_RULES",
        "m.tag": "TAG",
        "m.ignored_user_list": "IGNORED_USER_LIST",
    },
}

for _t_class, _types in _standard_types.items():
    for _t, _name in _types.items():
        _event_type = EventType(_t, _t_class)
        EventType.by_event_type[_t] = _event_type
        setattr(EventType, _name, _event_type)

EventType.ALL = EventType("__ALL__")
EventType.by_event_type["__ALL__"] = EventType.ALL


@dataclass
class BaseUnsigned:
    """Base unsigned information."""
    age: int = None


@dataclass
class BaseEvent:
    """Base event class. The only things an event **must** have are content and event type."""
    content: Obj
    type: EventType


@dataclass
class BaseRoomEvent(BaseEvent):
    """Base room event class. Room events must have a room ID, event ID, sender and timestamp in
    addition to the content and type in the base event."""
    room_id: RoomID
    event_id: EventID
    sender: UserID
    timestamp: int = attr.ib(metadata={"json": "origin_server_ts"})
