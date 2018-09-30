from typing import List
import attr

from .serializable import SerializableAttrs, SerializableEnum
from .event import EventType
from .primitive import RoomID, UserID


class EventFormat(SerializableEnum):
    CLIENT = "client"
    FEDERATION = "federation"


@attr.s(auto_attribs=True)
class EventFilter(SerializableAttrs['EventFilter']):
    limit: int = None
    not_senders: List[UserID] = None
    not_types: List[EventType] = None
    senders: List[UserID] = None
    types: List[EventType] = None


@attr.s(auto_attribs=True)
class RoomEventFilter(EventFilter, SerializableAttrs['RoomEventFilter']):
    not_rooms: List[RoomID] = None
    rooms: List[RoomID] = None
    contains_url: bool = False


@attr.s(auto_attribs=True)
class RoomFilter(SerializableAttrs['RoomFilter']):
    not_rooms: List[RoomID] = None
    rooms: List[RoomID] = None
    ephemeral: RoomEventFilter = None
    include_leave: bool = False
    state: RoomEventFilter = None
    timeline: RoomEventFilter = None
    account_data: RoomEventFilter = None


@attr.s(auto_attribs=True)
class Filter(SerializableAttrs['Filter']):
    event_fields: List[str]
    event_format: EventFormat
    presence: EventFilter
    account_data: EventFilter
    room: RoomFilter
