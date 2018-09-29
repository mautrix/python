from typing import NewType, Optional, List, Dict
import attr

from ....types import JSON
from .primitive import RoomID, UserID, EventID
from .serializable import SerializableEnum, SerializableAttrs

MatrixEvent = NewType("MatrixEvent", JSON)

STATE_EVENTS = ("m.room.aliases", "m.room.canonical_alias", "m.room.create", "m.room.join_rules",
                "m.room.member", "m.room.power_levels", "m.room.name", "m.room.topic",
                "m.room.avatar", "m.room.pinned_events")

MESSAGE_EVENTS = ("m.room.redaction", "m.room.message", "m.sticker")

EPHEMERAL_EVENTS = ("m.receipt", "m.typing")

ACCOUNT_DATA_EVENTS = ("m.direct", "m.push_rules", "m.tag")


class EventType(SerializableEnum):
    M_ROOM_ALIASES = "m.room.aliases"
    M_ROOM_CANONICAL_ALIAS = "m.room.canonical_alias"
    M_ROOM_CREATE = "m.room.create"
    M_ROOM_JOIN_RULES = "m.room.join_rules"
    M_ROOM_POWER_LEVELS = "m.room.power_levels"

    @property
    def is_state(self) -> bool:
        return self.value in STATE_EVENTS

    @property
    def is_ephemeral(self) -> bool:
        return self.value in EPHEMERAL_EVENTS

    @property
    def is_account_data(self) -> bool:
        return self.value in ACCOUNT_DATA_EVENTS


class Format(SerializableEnum):
    HTML = "org.matrix.custom.html"


class MessageType(SerializableEnum):
    TEXT = "m.text"
    EMOTE = "m.emote"
    NOTICE = "m.notice"
    IMAGE = "m.image"
    VIDEO = "m.video"
    AUDIO = "m.audio"
    FILE = "m.file"
    LOCATION = "m.location"


class Membership(SerializableEnum):
    JOIN = "join"
    LEAVE = "leave"
    INVITE = "invite"
    BAN = "ban"
    KNOCK = "knock"


@attr.s(auto_attribs=True)
class RelatesTo(SerializableAttrs['RelatesTo']):
    pass


@attr.s(auto_attribs=True)
class MatchedCommand(SerializableAttrs['MatchedCommand']):
    pass


@attr.s(auto_attribs=True)
class RoomTagInfo(SerializableAttrs['RoomTagInfo']):
    order: int = None


@attr.s(auto_attribs=True)
class PowerLevels(SerializableAttrs['PowerLevels']):
    users: Dict[str, int] = None
    users_default: int = 0

    events: Dict[str, int] = None
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
    membership: Membership = None
    avatar_url: str = None
    displayname: str = None
    reason: str = None
    third_party_invite: JSON = None


@attr.s(auto_attribs=True)
class EventContent(SerializableAttrs['EventContent']):
    msgtype: MessageType = None
    body: str = None
    format: Format = None
    formatted_body: str = None

    url: str = None

    membership: Membership = None
    member: Member = attr.ib(default=None, metadata={"flatten": True})

    relates_to: RelatesTo = attr.ib(default=None, metadata={"json": "m.relates_to"})
    command: MatchedCommand = attr.ib(default=None, metadata={"json": "m.command"})

    room_aliases: List[str] = attr.ib(default=None, metadata={"json": "aliases"})
    canonical_alias: str = attr.ib(default=None, metadata={"json": "alias"})

    room_name: str = attr.ib(default=None, metadata={"json": "name"})
    room_topic: str = attr.ib(default=None, metadata={"json": "topic"})

    power_levels: PowerLevels = attr.ib(default=None, metadata={"flatten": True})

    room_tags: Dict[str, RoomTagInfo] = attr.ib(default=None, metadata={"json": "tags"})

    typing_user_ids: List[str] = attr.ib(default=None, metadata={"json": "user_ids"})


@attr.s(auto_attribs=True)
class Unsigned(SerializableAttrs['Unsigned']):
    prev_content: EventContent = None
    prev_sender: str = None
    replaces_state: str = None
    age: int = None


@attr.s(auto_attribs=True)
class StrippedState(SerializableAttrs['StrippedState']):
    content: EventContent = None
    type: EventType = None
    state_key: str = None


@attr.s(auto_attribs=True)
class Event(SerializableAttrs['Event']):
    room_id: RoomID = None
    event_id: EventID = None
    state_key: str = None
    sender: UserID = None
    type: EventType = None
    timestamp: int = None
    content: EventContent = None

    redacts: str = None
    unsigned: Optional[Unsigned] = None
    invite_room_state: Optional[List[StrippedState]] = None
