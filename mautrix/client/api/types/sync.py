from typing import NewType, Dict, List
from attr import dataclass

from .util import SerializableAttrs
from .primitive import RoomID
from .event import StrippedState, EphemeralEvent, StateEvent, AccountDataEvent, Event

SyncToken = NewType("SyncToken", str)


@dataclass
class SyncEphemeral(SerializableAttrs['SyncEphemeral']):
    events: List[EphemeralEvent]


@dataclass
class SyncStateEvents(SerializableAttrs['SyncStateEvents']):
    events: List[StateEvent]


@dataclass
class SyncAccountData(SerializableAttrs['SyncAccountData']):
    events: List[AccountDataEvent]


@dataclass
class SyncRoomTimeline(SerializableAttrs['SyncRoomTimeline']):
    events: List[Event]


@dataclass
class SyncLeftRoom(SerializableAttrs['SyncLeftRoom']):
    state: SyncStateEvents
    timeline: SyncRoomTimeline
    account_data: SyncAccountData


@dataclass
class SyncUnreadNotificationCounts(SerializableAttrs['SyncUnreadNotificationCounts']):
    highlight_count: int
    notification_count: int


@dataclass
class SyncJoinedRoom(SyncLeftRoom, SerializableAttrs['SyncJoinedRoom']):
    ephemeral: SyncEphemeral
    unread_notifications: SyncUnreadNotificationCounts


@dataclass
class SyncInviteState(SerializableAttrs['SyncInviteState']):
    events: List[StrippedState]


@dataclass
class SyncInvitedRoom(SerializableAttrs['SyncInvitedRoom']):
    invite_state: SyncInviteState


@dataclass
class SyncRooms(SerializableAttrs['SyncRooms']):
    join: Dict[RoomID, SyncJoinedRoom]
    invite: Dict[RoomID, SyncInvitedRoom]
    leave: Dict[RoomID, SyncLeftRoom]


@dataclass
class SyncResult(SerializableAttrs['SyncResult']):
    next_batch: SyncToken
    rooms: SyncRooms
    presence: SyncPresence
    account_Data: SyncAccountData
