# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Dict

from attr import dataclass

from ..util import SerializableAttrs, SerializableEnum
from ..primitive import UserID, RoomID, EventID
from .base import BaseEvent


@dataclass
class TypingEventContent(SerializableAttrs['TypingEventContent']):
    user_ids: List[UserID]


@dataclass
class TypingEvent(BaseEvent, SerializableAttrs['TypingEvent']):
    room_id: RoomID
    content: TypingEventContent


class PresenceState(SerializableEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"


@dataclass
class PresenceEventContent(SerializableAttrs['PresenceEventContent']):
    presence: PresenceState
    last_active_ago: int = None
    status_msg: str = None
    currently_active: bool = None


@dataclass
class PresenceEvent(BaseEvent, SerializableAttrs['PresenceEvent']):
    sender: UserID
    content: PresenceEventContent


@dataclass
class SingleReceiptEventContent(SerializableAttrs['SingleReceiptEventContent']):
    ts: int


class ReceiptType(SerializableEnum):
    READ = "m.read"


ReceiptEventContent = Dict[EventID, Dict[ReceiptType, Dict[UserID, SingleReceiptEventContent]]]


@dataclass
class ReceiptEvent(BaseEvent, SerializableAttrs['ReceiptEvent']):
    room_id: RoomID
    content: ReceiptEventContent
