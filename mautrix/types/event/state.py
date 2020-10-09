# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, List, Dict, Union
from attr import dataclass
import attr

from ..primitive import JSON, UserID, EventID, ContentURI, RoomID, RoomAlias
from ..util import SerializableEnum, SerializableAttrs, Obj, deserializer
from .base import BaseRoomEvent, BaseUnsigned, EventType
from .encrypted import EncryptionAlgorithm


@dataclass
class PowerLevelStateEventContent(SerializableAttrs['PowerLevelStateEventContent']):
    """The content of a power level event."""
    users: Dict[UserID, int] = attr.ib(default=attr.Factory(dict), metadata={"omitempty": False})
    users_default: int = 0

    events: Dict[EventType, int] = attr.ib(default=attr.Factory(dict),
                                           metadata={"omitempty": False})
    events_default: int = 0

    state_default: int = 50

    invite: int = 50
    kick: int = 50
    ban: int = 50
    redact: int = 50

    def get_user_level(self, user_id: UserID) -> int:
        return int(self.users.get(user_id, self.users_default))

    def set_user_level(self, user_id: UserID, level: int) -> None:
        if level == self.users_default:
            del self.users[user_id]
        else:
            self.users[user_id] = level

    def ensure_user_level(self, user_id: UserID, level: int) -> bool:
        if self.get_user_level(user_id) != level:
            self.set_user_level(user_id, level)
            return True
        return False

    def get_event_level(self, event_type: EventType) -> int:
        return int(self.events.get(event_type, (self.state_default if event_type.is_state
                                                else self.events_default)))

    def set_event_level(self, event_type: EventType, level: int) -> None:
        if level == self.state_default if event_type.is_state else self.events_default:
            del self.events[event_type]
        else:
            self.events[event_type] = level

    def ensure_event_level(self, event_type: EventType, level: int) -> bool:
        if self.get_event_level(event_type) != level:
            self.set_event_level(event_type, level)
            return True
        return False


class Membership(SerializableEnum):
    """A room membership state."""
    JOIN = "join"
    LEAVE = "leave"
    INVITE = "invite"
    BAN = "ban"
    KNOCK = "knock"


@dataclass
class MemberStateEventContent(SerializableAttrs['MemberStateEventContent']):
    """The content of a membership event."""
    membership: Membership = Membership.LEAVE
    avatar_url: str = None
    displayname: str = None
    is_direct: bool = False
    reason: str = None
    third_party_invite: JSON = None


@dataclass
class AliasesStateEventContent(SerializableAttrs['AliasesStateEventContent']):
    aliases: List[RoomAlias] = None


@dataclass
class CanonicalAliasStateEventContent(SerializableAttrs['CanonicalAliasStateEventContent']):
    canonical_alias: RoomAlias = attr.ib(default=None, metadata={"json": "alias"})
    alt_aliases: List[RoomAlias] = attr.ib(factory=lambda: [])


@dataclass
class RoomNameStateEventContent(SerializableAttrs['RoomNameStateEventContent']):
    name: str = None


@dataclass
class RoomTopicStateEventContent(SerializableAttrs['RoomTopicStateEventContent']):
    topic: str = None


@dataclass
class RoomAvatarStateEventContent(SerializableAttrs['RoomAvatarStateEventContent']):
    url: Optional[ContentURI] = None


@dataclass
class RoomPinnedEventsStateEventContent(SerializableAttrs['RoomPinnedEventsStateEventContent']):
    pinned: List[EventID] = None


@dataclass
class RoomTombstoneStateEventContent(SerializableAttrs['RoomID, UserID']):
    body: str = None
    replacement_room: RoomID = None


@dataclass
class RoomEncryptionStateEventContent(SerializableAttrs['RoomEncryptionStateEventContent']):
    algorithm: EncryptionAlgorithm = None
    rotation_period_ms: int = 604800000
    rotation_period_msgs: int = 100


StateEventContent = Union[PowerLevelStateEventContent, MemberStateEventContent,
                          AliasesStateEventContent, CanonicalAliasStateEventContent,
                          RoomNameStateEventContent, RoomAvatarStateEventContent,
                          RoomTopicStateEventContent, RoomPinnedEventsStateEventContent,
                          RoomTombstoneStateEventContent, RoomEncryptionStateEventContent, Obj]


@dataclass
class StrippedStateUnsigned(BaseUnsigned, SerializableAttrs['StrippedStateUnsigned']):
    """Unsigned information sent with state events."""
    prev_content: StateEventContent = None
    prev_sender: UserID = None
    replaces_state: EventID = None


@dataclass
class StrippedStateEvent(SerializableAttrs['StrippedStateEvent']):
    """Stripped state events included with some invite events."""
    content: StateEventContent = None
    room_id: RoomID = None
    sender: UserID = None
    type: EventType = None
    state_key: str = None

    unsigned: Optional[StrippedStateUnsigned] = None

    @property
    def prev_content(self) -> StateEventContent:
        if self.unsigned and self.unsigned.prev_content:
            return self.unsigned.prev_content
        return state_event_content_map.get(self.type, Obj)()

    @classmethod
    def deserialize(cls, data: JSON) -> 'StrippedStateEvent':
        try:
            event_type = EventType.find(data.get("type", None))
            data.get("content", {})["__mautrix_event_type"] = event_type
            data.get("unsigned", {}).get("prev_content", {})["__mautrix_event_type"] = event_type
        except ValueError:
            pass
        return super().deserialize(data)


@dataclass
class StateUnsigned(StrippedStateUnsigned, SerializableAttrs['StateUnsigned']):
    invite_room_state: Optional[List[StrippedStateEvent]] = None


state_event_content_map = {
    EventType.ROOM_POWER_LEVELS: PowerLevelStateEventContent,
    EventType.ROOM_MEMBER: MemberStateEventContent,
    EventType.ROOM_ALIASES: AliasesStateEventContent,
    EventType.ROOM_PINNED_EVENTS: RoomPinnedEventsStateEventContent,
    EventType.ROOM_CANONICAL_ALIAS: CanonicalAliasStateEventContent,
    EventType.ROOM_NAME: RoomNameStateEventContent,
    EventType.ROOM_AVATAR: RoomAvatarStateEventContent,
    EventType.ROOM_TOPIC: RoomTopicStateEventContent,
    EventType.ROOM_TOMBSTONE: RoomTombstoneStateEventContent,
    EventType.ROOM_ENCRYPTION: RoomEncryptionStateEventContent,
}


@dataclass
class StateEvent(BaseRoomEvent, SerializableAttrs['StateEvent']):
    """A room state event."""
    state_key: str
    content: StateEventContent
    unsigned: Optional[StateUnsigned] = None

    @property
    def prev_content(self) -> StateEventContent:
        if self.unsigned and self.unsigned.prev_content:
            return self.unsigned.prev_content
        return state_event_content_map.get(self.type, Obj)()

    @classmethod
    def deserialize(cls, data: JSON) -> 'StateEvent':
        try:
            event_type = EventType.find(data.get("type"))
            data.get("content", {})["__mautrix_event_type"] = event_type
            if "prev_content" in data and "prev_content" not in data.get("unsigned", {}):
                data.setdefault("unsigned", {})["prev_content"] = data["prev_content"]
            data.get("unsigned", {}).get("prev_content", {})["__mautrix_event_type"] = event_type
        except ValueError:
            return Obj(**data)
        return super().deserialize(data)

    @staticmethod
    @deserializer(StateEventContent)
    def deserialize_content(data: JSON) -> StateEventContent:
        evt_type = data.pop("__mautrix_event_type", None)
        content_type = state_event_content_map.get(evt_type, None)
        if not content_type:
            return Obj(**data)
        return content_type.deserialize(data)
