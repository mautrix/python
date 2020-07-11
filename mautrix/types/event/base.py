# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional

from attr import dataclass
import attr

from ..primitive import RoomID, UserID, EventID
from ..util import Obj, SerializableAttrs
from .type import EventType


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


@dataclass
class GenericEvent(BaseEvent, SerializableAttrs['GenericEvent']):
    """
    An event class that contains all possible top-level event keys and uses generic Obj's for object
    keys (content and unsigned)
    """
    content: Obj
    type: EventType
    room_id: Optional[RoomID] = None
    event_id: Optional[EventID] = None
    sender: Optional[UserID] = None
    timestamp: Optional[int] = None
    state_key: Optional[str] = None
    unsigned: Obj = None
    redacts: Optional[EventID] = None
