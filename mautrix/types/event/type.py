# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, Optional
import json

from ..primitive import JSON
from ..util import SerializableEnum, Serializable


class EventType(Serializable):
    """An event type."""
    by_event_type: Dict[str, 'EventType'] = {}

    class Class(SerializableEnum):
        UNKNOWN = "unknown"
        STATE = "state"
        MESSAGE = "message"
        ACCOUNT_DATA = "account_data"
        EPHEMERAL = "ephemeral"
        TO_DEVICE = "to_device"

    __slots__ = ("t", "t_class")

    def __init__(self, t: str, t_class: Class) -> None:
        object.__setattr__(self, "t", t)
        object.__setattr__(self, "t_class", t_class)
        if t not in self.by_event_type:
            self.by_event_type[t] = self

    def serialize(self) -> JSON:
        return self.t

    @classmethod
    def deserialize(cls, raw: JSON) -> Any:
        return cls.find(raw)

    @classmethod
    def find(cls, t: str, t_class: Optional[Class] = None) -> 'EventType':
        try:
            return cls.by_event_type[t].with_class(t_class)
        except KeyError:
            return EventType(t, t_class=t_class or cls.Class.UNKNOWN)

    def json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def parse_json(cls, data: str) -> 'EventType':
        return cls.deserialize(json.loads(data))

    def __setattr__(self, *args, **kwargs) -> None:
        raise TypeError("EventTypes are frozen")

    def __delattr__(self, *args, **kwargs) -> None:
        raise TypeError("EventTypes are frozen")

    def __str__(self):
        return self.t

    def __repr__(self):
        return f'EventType("{self.t}", EventType.Class.{self.t_class.name})'

    def __hash__(self):
        return hash(self.t) ^ hash(self.t_class)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, EventType):
            return False
        return self.t == other.t and self.t_class == other.t_class

    def with_class(self, t_class: Class) -> 'EventType':
        if t_class is None or self.t_class == t_class:
            return self
        return EventType(t=self.t, t_class=t_class)

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

    @property
    def is_to_device(self) -> bool:
        """Whether or not the event is a to-device event."""
        return self.t_class == EventType.Class.TO_DEVICE


_standard_types = {
    EventType.Class.STATE: {
        "m.room.aliases": "ROOM_ALIASES",
        "m.room.canonical_alias": "ROOM_CANONICAL_ALIAS",
        "m.room.create": "ROOM_CREATE",
        "m.room.join_rules": "ROOM_JOIN_RULES",
        "m.room.member": "ROOM_MEMBER",
        "m.room.power_levels": "ROOM_POWER_LEVELS",
        "m.room.history_visibility": "ROOM_HISTORY_VISIBILITY",
        "m.room.name": "ROOM_NAME",
        "m.room.topic": "ROOM_TOPIC",
        "m.room.avatar": "ROOM_AVATAR",
        "m.room.pinned_events": "ROOM_PINNED_EVENTS",
        "m.room.tombstone": "ROOM_TOMBSTONE",
        "m.room.encryption": "ROOM_ENCRYPTION",
    },
    EventType.Class.MESSAGE: {
        "m.room.redaction": "ROOM_REDACTION",
        "m.room.message": "ROOM_MESSAGE",
        "m.room.encrypted": "ROOM_ENCRYPTED",
        "m.sticker": "STICKER",
        "m.reaction": "REACTION",
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
    EventType.Class.TO_DEVICE: {
        "m.room.encrypted": "TO_DEVICE_ENCRYPTED",
        "m.room_key": "ROOM_KEY",
        "m.room_key.withheld": "ROOM_KEY_WITHHELD",
        "org.matrix.room_key.withheld": "ORG_MATRIX_ROOM_KEY_WITHHELD",
        "m.room_key_request": "ROOM_KEY_REQUEST",
        "m.forwarded_room_key": "FORWARDED_ROOM_KEY",
    },
}

for _t_class, _types in _standard_types.items():
    for _t, _name in _types.items():
        _event_type = EventType(t=_t, t_class=_t_class)
        setattr(EventType, _name, _event_type)

EventType.ALL = EventType(t="__ALL__", t_class=EventType.Class.UNKNOWN)
EventType.by_event_type["__ALL__"] = EventType.ALL
