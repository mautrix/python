import attr

from ....types import JSON
from .primitive import RoomID, UserID, EventID
from .serializable import SerializableEnum, SerializableAttrs

STATE_EVENTS = ("m.room.aliases", "m.room.canonical_alias", "m.room.create", "m.room.join_rules",
                "m.room.member", "m.room.power_levels", "m.room.name", "m.room.topic",
                "m.room.avatar", "m.room.pinned_events")

MESSAGE_EVENTS = ("m.room.redaction", "m.room.message", "m.sticker")

EPHEMERAL_EVENTS = ("m.receipt", "m.typing", "m.presence")

ACCOUNT_DATA_EVENTS = ("m.direct", "m.push_rules", "m.tag")


class EventType(SerializableEnum):
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

    @property
    def is_state(self) -> bool:
        return self.value in STATE_EVENTS

    @property
    def is_ephemeral(self) -> bool:
        return self.value in EPHEMERAL_EVENTS

    @property
    def is_account_data(self) -> bool:
        return self.value in ACCOUNT_DATA_EVENTS


class BaseUnsigned:
    age: int = None


class BaseEvent:
    content: JSON = None
    type: EventType = None


class BaseRoomEvent(BaseEvent):
    room_id: RoomID = None
    event_id: EventID = None
    sender: UserID = None
    timestamp: int = None
