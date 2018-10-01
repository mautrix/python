from typing import Optional, List, Dict
import attr

from .....types import JSON
from ..primitive import UserID
from ..util import SerializableEnum, SerializableAttrs
from .base import BaseRoomEvent, BaseUnsigned, EventType


class Membership(SerializableEnum):
    """A room membership state."""
    JOIN = "join"
    LEAVE = "leave"
    INVITE = "invite"
    BAN = "ban"
    KNOCK = "knock"


@attr.s(auto_attribs=True)
class PowerLevels(SerializableAttrs['PowerLevels']):
    """The full content of a power level event."""
    users: Dict[str, int] = attr.ib(default={}, metadata={"omitempty": False})
    users_default: int = 0

    events: Dict[str, int] = attr.ib(default={}, metadata={"omitempty": False})
    events_default: int = 0

    state_default: int = 50

    invite: int = 50
    kick: int = 50
    ban: int = 50
    redact: int = 50

    def get_user_level(self, user_id: UserID) -> int:
        return self.users.get(user_id, self.users_default)

    def set_user_level(self, user_id: UserID, level: int) -> None:
        if level == self.users_default:
            del self.users[user_id]
        else:
            self.users[user_id] = level

    def ensure_user_level(self, user_id: UserID, level: int) -> bool:
        if self.get_user_level(user_id) != level:
            self.set_user_level(user_id, level)
            return True
        return False

    def get_event_level(self, event_type: EventType) -> int:
        return self.events.get(event_type.value,
                               self.state_default if event_type.is_state else self.events_default)

    def set_event_level(self, event_type: EventType, level: int) -> None:
        if level == self.state_default if event_type.is_state else self.events_default:
            del self.events[event_type.value]
        else:
            self.events[event_type.value] = level

    def ensure_event_level(self, event_type: EventType, level: int) -> bool:
        if self.get_event_level(event_type) != level:
            self.set_event_level(event_type, level)
            return True
        return False


@attr.s(auto_attribs=True)
class Member(SerializableAttrs['Member']):
    """The content of a membership event."""
    membership: Membership = None
    avatar_url: str = None
    displayname: str = None
    reason: str = None
    third_party_invite: JSON = None


@attr.s(auto_attribs=True)
class StateEventContent(SerializableAttrs['StateEventContent']):
    """The content of a state event. The contents of all known different state event types are
    available in this object. You should check :StateEvent:`type` to find the specific field to
    access"""
    membership: Membership = None
    member: Member = attr.ib(default=None, metadata={"flatten": True})

    room_aliases: List[str] = attr.ib(default=None, metadata={"json": "aliases"})

    canonical_alias: str = attr.ib(default=None, metadata={"json": "alias"})

    room_name: str = attr.ib(default=None, metadata={"json": "name"})

    room_topic: str = attr.ib(default=None, metadata={"json": "topic"})

    power_levels: PowerLevels = attr.ib(default=None, metadata={"flatten": True})

    typing_user_ids: List[str] = attr.ib(default=None, metadata={"json": "user_ids"})


@attr.s(auto_attribs=True)
class StrippedState(SerializableAttrs['StrippedState']):
    """Stripped state events included with some invite events."""
    content: StateEventContent = None
    type: EventType = None
    state_key: str = None


@attr.s(auto_attribs=True)
class StateUnsigned(BaseUnsigned, SerializableAttrs['StateUnsigned']):
    """Unsigned information sent with state events."""
    prev_content: StateEventContent = None
    prev_sender: str = None
    replaces_state: str = None
    invite_room_state: Optional[List[StrippedState]] = None


@attr.s(auto_attribs=True)
class StateEvent(BaseRoomEvent, SerializableAttrs['StateEvent']):
    """A room state event."""
    state_key: str
    content: StateEventContent
    unsigned: Optional[StateUnsigned] = None
