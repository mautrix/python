from attr import dataclass
import attr

from ..primitive import RoomID, UserID, EventID
from ..util import SerializableEnum, Obj

STATE_EVENTS = ("m.room.aliases", "m.room.canonical_alias", "m.room.create", "m.room.join_rules",
                "m.room.member", "m.room.power_levels", "m.room.name", "m.room.topic",
                "m.room.avatar", "m.room.pinned_events")

MESSAGE_EVENTS = ("m.room.redaction", "m.room.message", "m.sticker")

EPHEMERAL_EVENTS = ("m.receipt", "m.typing", "m.presence")

ACCOUNT_DATA_EVENTS = ("m.direct", "m.push_rules", "m.tag", "m.ignored_user_list")


class EventType(SerializableEnum):
    """An event type."""
    ROOM_ALIASES = "m.room.aliases"
    ROOM_CANONICAL_ALIAS = "m.room.canonical_alias"
    ROOM_CREATE = "m.room.create"
    ROOM_JOIN_RULES = "m.room.join_rules"
    ROOM_MEMBER = "m.room.member"
    ROOM_POWER_LEVELS = "m.room.power_levels"
    ROOM_NAME = "m.room.name"
    ROOM_TOPIC = "m.room.topic"
    ROOM_AVATAR = "m.room.avatar"
    ROOM_PINNED_EVENTS = "m.room.pinned_events"

    ROOM_REDACTION = "m.room.redaction"
    ROOM_MESSAGE = "m.room.message"
    STICKER = "m.sticker"

    RECEIPT = "m.receipt"
    TYPING = "m.typing"
    PRESENCE = "m.presence"

    DIRECT = "m.direct"
    PUSH_RULES = "m.push_rules"
    TAG = "m.tag"
    IGNORED_USER_LIST = "m.ignored_user_list"

    @property
    def is_message(self) -> bool:
        """Whether or not the event is a message event."""
        return self.value in EPHEMERAL_EVENTS

    @property
    def is_state(self) -> bool:
        """Whether or not the event is a state event."""
        return self.value in STATE_EVENTS

    @property
    def is_ephemeral(self) -> bool:
        """Whether or not the event is ephemeral."""
        return self.value in EPHEMERAL_EVENTS

    @property
    def is_account_data(self) -> bool:
        """Whether or not the event is an account data event."""
        return self.value in ACCOUNT_DATA_EVENTS


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
