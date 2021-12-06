# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Optional
import json

from ..primitive import JSON
from ..util import ExtensibleEnum, Serializable, SerializableEnum


class RoomType(ExtensibleEnum):
    SPACE = "m.space"


class EventType(Serializable):
    """
    An immutable enum-like class that represents a specific Matrix event type.

    In addition to the plain event type string, this also includes the context that the event is
    used in (see: :class:`Class`). Comparing ``EventType`` instances for equality will check both
    the type string and the class.

    The idea behind the wrapper is that incoming event parsers will always create an ``EventType``
    instance with the correct class, regardless of what the usual context for the event is. Then
    when the event is being handled, the type will not be equal to ``EventType`` instances with a
    different class. For example, if someone sends a non-state ``m.room.name`` event, checking
    ``if event.type == EventType.ROOM_NAME`` would return ``False``, because the class would be
    different. Bugs caused by not checking the context of an event (especially state event vs
    message event) were very common in the past, and using a wrapper like this helps prevent them.
    """

    _by_event_type = {}

    class Class(SerializableEnum):
        """The context that an event type is used in."""

        UNKNOWN = "unknown"

        STATE = "state"
        """Room state events"""

        MESSAGE = "message"
        """Room message events, i.e. room events that are not state events"""

        ACCOUNT_DATA = "account_data"
        """Account data events, user-specific storage used for synchronizing info between clients.
        Can be global or room-specific."""

        EPHEMERAL = "ephemeral"
        """Ephemeral events. Currently only typing notifications, read receipts and presence are
        in this class, as custom ephemeral events are not yet possible."""

        TO_DEVICE = "to_device"
        """Device-to-device events, primarily used for exchanging encryption keys"""

    __slots__ = ("t", "t_class")

    t: str
    """The type string of the event."""
    t_class: Class
    """The context where the event appeared."""

    def __init__(self, t: str, t_class: Class) -> None:
        object.__setattr__(self, "t", t)
        object.__setattr__(self, "t_class", t_class)
        if t not in self._by_event_type:
            self._by_event_type[t] = self

    def serialize(self) -> JSON:
        return self.t

    @classmethod
    def deserialize(cls, raw: JSON) -> Any:
        return cls.find(raw)

    @classmethod
    def find(cls, t: str, t_class: Optional[Class] = None) -> "EventType":
        """
        Create a new ``EventType`` instance with the given type and class.

        If an ``EventType`` instance with the same type string and class has been created before,
        or if no class is specified here, this will return the same instance instead of making a
        new one.

        Examples:
            >>> from mautrix.client import Client
            >>> from mautrix.types import EventType
            >>> MY_CUSTOM_TYPE = EventType.find("com.example.custom_event", EventType.Class.STATE)
            >>> client = Client(...)
            >>> @client.on(MY_CUSTOM_TYPE)
            ... async def handle_event(evt): ...

        Args:
            t: The type string.
            t_class: The class of the event type.

        Returns:
            An ``EventType`` instance with the given parameters.
        """
        try:
            return cls._by_event_type[t].with_class(t_class)
        except KeyError:
            return EventType(t, t_class=t_class or cls.Class.UNKNOWN)

    def json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def parse_json(cls, data: str) -> "EventType":
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

    def with_class(self, t_class: Optional[Class]) -> "EventType":
        """Return a copy of this ``EventType`` with the given class. If the given class is the
        same as what this instance has, or if the given class is ``None``, this returns ``self``
        instead of making a copy."""
        if t_class is None or self.t_class == t_class:
            return self
        return EventType(t=self.t, t_class=t_class)

    @property
    def is_message(self) -> bool:
        """A shortcut for ``type.t_class == EventType.Class.MESSAGE``"""
        return self.t_class == EventType.Class.MESSAGE

    @property
    def is_state(self) -> bool:
        """A shortcut for ``type.t_class == EventType.Class.STATE``"""
        return self.t_class == EventType.Class.STATE

    @property
    def is_ephemeral(self) -> bool:
        """A shortcut for ``type.t_class == EventType.Class.EPHEMERAL``"""
        return self.t_class == EventType.Class.EPHEMERAL

    @property
    def is_account_data(self) -> bool:
        """A shortcut for ``type.t_class == EventType.Class.ACCOUNT_DATA``"""
        return self.t_class == EventType.Class.ACCOUNT_DATA

    @property
    def is_to_device(self) -> bool:
        """A shortcut for ``type.t_class == EventType.Class.TO_DEVICE``"""
        return self.t_class == EventType.Class.TO_DEVICE


_standard_types = {
    EventType.Class.STATE: {
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
        "m.space.child": "SPACE_CHILD",
        "m.space.parent": "SPACE_PARENT",
    },
    EventType.Class.MESSAGE: {
        "m.room.redaction": "ROOM_REDACTION",
        "m.room.message": "ROOM_MESSAGE",
        "m.room.encrypted": "ROOM_ENCRYPTED",
        "m.sticker": "STICKER",
        "m.reaction": "REACTION",
        "m.call.invite": "CALL_INVITE",
        "m.call.candidates": "CALL_CANDIDATES",
        "m.call.select_answer": "CALL_SELECT_ANSWER",
        "m.call.answer": "CALL_ANSWER",
        "m.call.hangup": "CALL_HANGUP",
        "m.call.reject": "CALL_REJECT",
        "m.call.negotiate": "CALL_NEGOTIATE",
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
        "m.dummy": "TO_DEVICE_DUMMY",
    },
    EventType.Class.UNKNOWN: {
        "__ALL__": "ALL",  # This is not a real event type
    },
}

for _t_class, _types in _standard_types.items():
    for _t, _name in _types.items():
        _event_type = EventType(t=_t, t_class=_t_class)
        setattr(EventType, _name, _event_type)
