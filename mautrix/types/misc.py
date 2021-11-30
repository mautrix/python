# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, NewType, NamedTuple, Dict
from enum import Enum

from attr import dataclass
import attr

from .primitive import RoomID, RoomAlias, SyncToken, ContentURI, UserID, BatchID, EventID
from .util import SerializableAttrs
from .event import Event


@dataclass
class DeviceLists(SerializableAttrs):
    changed: List[UserID] = attr.ib(factory=lambda: [])
    left: List[UserID] = attr.ib(factory=lambda: [])


@dataclass
class DeviceOTKCount(SerializableAttrs):
    curve25519: int
    signed_curve25519: int


class RoomCreatePreset(Enum):
    """
    Room creation preset, as specified in the `createRoom endpoint`_

    .. _createRoom endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-createroom
    """
    PRIVATE = "private_chat"
    TRUSTED_PRIVATE = "trusted_private_chat"
    PUBLIC = "public_chat"


class RoomDirectoryVisibility(Enum):
    """
    Room directory visibility, as specified in the `createRoom endpoint`_

    .. _createRoom endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-createroom
    """
    PRIVATE = "private"
    PUBLIC = "public"


class PaginationDirection(Enum):
    """
    Pagination direction, as specified in the `pagination section`_.

    .. _pagination section:
        https://matrix.org/docs/spec/client_server/latest#pagination
    """
    FORWARD = "f"
    BACKWARD = "b"


@dataclass
class RoomAliasInfo(SerializableAttrs):
    """
    Room alias query result, as specified in the `alias resolve endpoint`_

    .. _alias resolve endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#get-matrix-client-r0-directory-room-roomalias
    """
    room_id: RoomID = None
    """The room ID for this room alias."""

    servers: List[str] = None
    """A list of servers that are aware of this room alias."""


DirectoryPaginationToken = NewType("DirectoryPaginationToken", str)


@dataclass
class PublicRoomInfo(SerializableAttrs):
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
class RoomDirectoryResponse(SerializableAttrs):
    chunk: List[PublicRoomInfo]
    next_batch: DirectoryPaginationToken = None
    prev_batch: DirectoryPaginationToken = None
    total_room_count_estimate: int = None


PaginatedMessages = NamedTuple("PaginatedMessages", start=SyncToken, end=SyncToken,
                               events=List[Event])


@dataclass
class VersionsResponse(SerializableAttrs):
    versions: List[str]
    unstable_features: Dict[str, bool] = attr.ib(factory=lambda: {})


@dataclass
class BatchSendResponse(SerializableAttrs):
    state_event_ids: List[EventID]
    event_ids: List[EventID]

    insertion_event_id: EventID
    batch_event_id: EventID
    base_insertion_event_id: EventID

    next_batch_id: BatchID
