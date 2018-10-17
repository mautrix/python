from typing import Optional, List, Dict, Union
from attr import dataclass
import attr

from .....api import JSON
from ..primitive import UserID, EventID, ContentURI, RoomID
from ..util import SerializableEnum, SerializableAttrs, Obj, deserializer
from .base import BaseRoomEvent, BaseUnsigned, EventType


@dataclass
class PowerLevelStateEventContent(SerializableAttrs['PowerLevelStateEventContent']):
    """The content of a power level event."""
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


class Membership(SerializableEnum):
    """A room membership state."""
    JOIN = "join"
    LEAVE = "leave"
    INVITE = "invite"
    BAN = "ban"
    KNOCK = "knock"


@dataclass
class MemberStateEventContent(SerializableAttrs['MemberStateEventContent']):
    """The content of a membership event."""
    membership: Membership
    avatar_url: str = None
    displayname: str = None
    reason: str = None
    third_party_invite: JSON = None


@dataclass
class AliasesStateEventContent(SerializableAttrs['AliasesStateEventContent']):
    aliases: List[str] = None


@dataclass
class CanonicalAliasStateEventContent(SerializableAttrs['CanonicalAliasStateEventContent']):
    canonical_alias: str = attr.ib(default=None, metadata={"json": "alias"})


@dataclass
class RoomNameStateEventContent(SerializableAttrs['RoomNameStateEventContent']):
    name: str


@dataclass
class RoomTopicStateEventContent(SerializableAttrs['RoomTopicStateEventContent']):
    topic: str


@dataclass
class RoomAvatarStateEventContent(SerializableAttrs['RoomAvatarStateEventContent']):
    url: ContentURI


StateEventContent = Union[PowerLevelStateEventContent, MemberStateEventContent,
                          AliasesStateEventContent, CanonicalAliasStateEventContent,
                          RoomNameStateEventContent, RoomAvatarStateEventContent,
                          RoomTopicStateEventContent, Obj]


@dataclass
class StrippedStateEvent(SerializableAttrs['StrippedStateEvent']):
    """Stripped state events included with some invite events."""
    content: StateEventContent = None
    room_id: RoomID = None
    type: EventType = None
    state_key: str = None

    _unsigned: Optional['StateUnsigned'] = None

    @property
    def unsigned(self) -> 'StateUnsigned':
        if not self._unsigned:
            self._unsigned = StateUnsigned()
        return self._unsigned

    @unsigned.setter
    def unsigned(self, value: 'StateUnsigned') -> None:
        self._unsigned = value

    @classmethod
    def deserialize(cls, data: JSON) -> 'StrippedStateEvent':
        try:
            data.get("content", {})["__mautrix_event_type"] = EventType(data.get("type", None))
        except ValueError:
            pass
        return super().deserialize(data)


@dataclass
class StateUnsigned(BaseUnsigned, SerializableAttrs['StateUnsigned']):
    """Unsigned information sent with state events."""
    prev_content: StateEventContent = None
    prev_sender: UserID = None
    replaces_state: EventID = None
    invite_room_state: Optional[List[StrippedStateEvent]] = None


state_event_content_map = {
    EventType.ROOM_POWER_LEVELS: PowerLevelStateEventContent,
    EventType.ROOM_MEMBER: MemberStateEventContent,
    EventType.ROOM_ALIASES: AliasesStateEventContent,
    EventType.ROOM_CANONICAL_ALIAS: CanonicalAliasStateEventContent,
    EventType.ROOM_NAME: RoomNameStateEventContent,
    EventType.ROOM_AVATAR: RoomAvatarStateEventContent,
    EventType.ROOM_TOPIC: RoomTopicStateEventContent,
}


@dataclass
class StateEvent(BaseRoomEvent, SerializableAttrs['StateEvent']):
    """A room state event."""
    state_key: str
    content: StateEventContent
    _unsigned: Optional[StateUnsigned] = None

    @property
    def unsigned(self) -> StateUnsigned:
        if not self._unsigned:
            self._unsigned = StateUnsigned()
        return self._unsigned

    @unsigned.setter
    def unsigned(self, value: StateUnsigned) -> None:
        self._unsigned = value

    @classmethod
    def deserialize(cls, data: JSON) -> 'StateEvent':
        try:
            event_type = EventType(data.get("type"))
            data.get("content", {})["__mautrix_event_type"] = event_type
            data.get("unsigned", {}).get("prev_content", {})["__mautrix_event_type"] = event_type
        except ValueError:
            return Obj(**data)
        return super().deserialize(data)

    @staticmethod
    @deserializer(StateEventContent)
    def deserialize_content(data: JSON) -> StateEventContent:
        evt_type = data.pop("__mautrix_event_type", None)
        content_type = state_event_content_map.get(evt_type, None)
        if not content_type:
            return Obj(**data)
        return content_type.deserialize(data)
