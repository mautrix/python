from enum import Enum
from typing import List, NewType
import attr

from .primitive import RoomID, RoomAlias
from .util import SerializableAttrs


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


@attr.s(auto_attribs=True)
class RoomAliasInfo(SerializableAttrs['RoomAliasInfo']):
    room_id: RoomID = None
    servers: List[str] = None


DirectoryPaginationToken = NewType("DirectoryPaginationToken", str)


@attr.s(auto_attribs=True)
class PublicRoomInfo(SerializableAttrs['PublicRoomInfo']):
    room_id: RoomID

    num_joined_members: int

    world_readable: bool
    guests_can_join: bool

    name: str = None
    topic: str = None
    avatar_url: str = None

    aliases: List[RoomAlias] = None
    canonical_alias: RoomAlias = None


@attr.s(auto_attribs=True)
class RoomDirectoryResponse(SerializableAttrs['RoomDirectoryResponse']):
    chunk: List[PublicRoomInfo]
    next_batch: DirectoryPaginationToken = None
    prev_batch: DirectoryPaginationToken = None
    total_room_count_estimate: int = None
