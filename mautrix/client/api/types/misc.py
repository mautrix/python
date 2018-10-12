from enum import Enum
from typing import List, NewType, NamedTuple
from attr import dataclass

from .primitive import RoomID, RoomAlias, SyncToken, ContentURI
from .util import SerializableAttrs, SerializableEnum
from .event import Event


class RoomCreatePreset(Enum):
    PRIVATE = "private_chat"
    TRUSTED_PRIVATE = "trusted_private_chat"
    PUBLIC = "public_chat"


class RoomDirectoryVisibility(Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class PaginationDirection(Enum):
    FORWARD = "f"
    BACKWARD = "b"


@dataclass
class RoomAliasInfo(SerializableAttrs['RoomAliasInfo']):
    room_id: RoomID = None
    servers: List[str] = None


DirectoryPaginationToken = NewType("DirectoryPaginationToken", str)


@dataclass
class PublicRoomInfo(SerializableAttrs['PublicRoomInfo']):
    room_id: RoomID

    num_joined_members: int

    world_readable: bool
    guests_can_join: bool

    name: str = None
    topic: str = None
    avatar_url: ContentURI = None

    aliases: List[RoomAlias] = None
    canonical_alias: RoomAlias = None


@dataclass
class RoomDirectoryResponse(SerializableAttrs['RoomDirectoryResponse']):
    chunk: List[PublicRoomInfo]
    next_batch: DirectoryPaginationToken = None
    prev_batch: DirectoryPaginationToken = None
    total_room_count_estimate: int = None


PaginatedMessages = NamedTuple("PaginatedMessages", start=SyncToken, end=SyncToken,
                               events=List[Event])


class PresenceState(SerializableEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"


@dataclass
class Presence(SerializableAttrs['Presence']):
    presence: PresenceState
    last_active_ago: int = None
    status_msg: str = None
    currently_active: bool = None
