# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, NamedTuple, NewType, Optional
from enum import Enum

from attr import dataclass
import attr

from .event import Event, StateEvent
from .primitive import BatchID, ContentURI, EventID, RoomAlias, RoomID, SyncToken, UserID
from .util import SerializableAttrs


@dataclass
class DeviceLists(SerializableAttrs):
    changed: List[UserID] = attr.ib(factory=lambda: [])
    left: List[UserID] = attr.ib(factory=lambda: [])

    def __bool__(self) -> bool:
        return bool(self.changed or self.left)


@dataclass
class DeviceOTKCount(SerializableAttrs):
    signed_curve25519: int = 0
    curve25519: int = 0


class RoomCreatePreset(Enum):
    """
    Room creation preset, as specified in the `createRoom endpoint`_

    .. _createRoom endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#post_matrixclientv3createroom
    """

    PRIVATE = "private_chat"
    TRUSTED_PRIVATE = "trusted_private_chat"
    PUBLIC = "public_chat"


class RoomDirectoryVisibility(Enum):
    """
    Room directory visibility, as specified in the `createRoom endpoint`_

    .. _createRoom endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#post_matrixclientv3createroom
    """

    PRIVATE = "private"
    PUBLIC = "public"


class PaginationDirection(Enum):
    """Pagination direction used in various endpoints that support pagination."""

    FORWARD = "f"
    BACKWARD = "b"


@dataclass
class RoomAliasInfo(SerializableAttrs):
    """
    Room alias query result, as specified in the `alias resolve endpoint`_

    .. _alias resolve endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#get_matrixclientv3directoryroomroomalias
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


PaginatedMessages = NamedTuple(
    "PaginatedMessages", start=SyncToken, end=SyncToken, events=List[Event]
)


@dataclass
class EventContext(SerializableAttrs):
    end: SyncToken
    start: SyncToken
    event: Event
    events_after: List[Event]
    events_before: List[Event]
    state: List[StateEvent]


@dataclass
class BatchSendResponse(SerializableAttrs):
    state_event_ids: List[EventID]
    event_ids: List[EventID]

    insertion_event_id: EventID
    batch_event_id: EventID
    next_batch_id: BatchID
    base_insertion_event_id: Optional[EventID] = None
