# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List
from attr import dataclass

from .util import SerializableAttrs, SerializableEnum
from .event import EventType
from .primitive import RoomID, UserID


class EventFormat(SerializableEnum):
    CLIENT = "client"
    FEDERATION = "federation"


@dataclass
class EventFilter(SerializableAttrs['EventFilter']):
    limit: int = None
    not_senders: List[UserID] = None
    not_types: List[EventType] = None
    senders: List[UserID] = None
    types: List[EventType] = None


@dataclass
class RoomEventFilter(EventFilter, SerializableAttrs['RoomEventFilter']):
    not_rooms: List[RoomID] = None
    rooms: List[RoomID] = None
    contains_url: bool = None


@dataclass
class RoomFilter(SerializableAttrs['RoomFilter']):
    not_rooms: List[RoomID] = None
    rooms: List[RoomID] = None
    ephemeral: RoomEventFilter = None
    include_leave: bool = False
    state: RoomEventFilter = None
    timeline: RoomEventFilter = None
    account_data: RoomEventFilter = None


@dataclass
class Filter(SerializableAttrs['Filter']):
    event_fields: List[str] = None
    event_format: EventFormat = None
    presence: EventFilter = None
    account_data: EventFilter = None
    room: RoomFilter = None
