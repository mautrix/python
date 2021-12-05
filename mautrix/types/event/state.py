# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Optional, Union

from attr import dataclass
import attr

from ..primitive import JSON, ContentURI, EventID, RoomAlias, RoomID, UserID
from ..util import Obj, SerializableAttrs, SerializableEnum, deserializer, field
from .base import BaseRoomEvent, BaseUnsigned
from .encrypted import EncryptionAlgorithm
from .type import EventType, RoomType


@dataclass
class PowerLevelStateEventContent(SerializableAttrs):
    """The content of a power level event."""

    users: Dict[UserID, int] = attr.ib(default=attr.Factory(dict), metadata={"omitempty": False})
    users_default: int = 0

    events: Dict[EventType, int] = attr.ib(
        default=attr.Factory(dict), metadata={"omitempty": False}
    )
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
        return int(
            self.events.get(
                event_type, (self.state_default if event_type.is_state else self.events_default)
            )
        )

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
    """
    The membership state of a user in a room as specified in section `8.4 Room membership`_ of the
    spec.

    .. _8.4 Room membership: https://spec.matrix.org/v1.1/client-server-api/#room-membership
    """

    JOIN = "join"
    LEAVE = "leave"
    INVITE = "invite"
    BAN = "ban"
    KNOCK = "knock"


@dataclass
class MemberStateEventContent(SerializableAttrs):
    """The content of a membership event. `Spec link`_

    .. _Spec link: https://spec.matrix.org/v1.1/client-server-api/#mroommember"""

    membership: Membership = Membership.LEAVE
    avatar_url: ContentURI = None
    displayname: str = None
    is_direct: bool = False
    reason: str = None
    third_party_invite: JSON = None


@dataclass
class CanonicalAliasStateEventContent(SerializableAttrs):
    """
    The content of a ``m.room.canonical_alias`` event (:attr:`EventType.ROOM_CANONICAL_ALIAS`).

    This event is used to inform the room about which alias should be considered the canonical one,
    and which other aliases point to the room. This could be for display purposes or as suggestion
    to users which alias to use to advertise and access the room.

    See also: `m.room.canonical_alias in the spec`_

    .. _m.room.canonical_alias in the spec: https://spec.matrix.org/v1.1/client-server-api/#mroomcanonical_alias
    """

    canonical_alias: RoomAlias = attr.ib(default=None, metadata={"json": "alias"})
    alt_aliases: List[RoomAlias] = attr.ib(factory=lambda: [])


@dataclass
class RoomNameStateEventContent(SerializableAttrs):
    name: str = None


@dataclass
class RoomTopicStateEventContent(SerializableAttrs):
    topic: str = None


@dataclass
class RoomAvatarStateEventContent(SerializableAttrs):
    url: Optional[ContentURI] = None


class JoinRule(SerializableEnum):
    PUBLIC = "public"
    KNOCK = "knock"
    RESTRICTED = "restricted"
    INVITE = "invite"
    PRIVATE = "private"


class JoinRestrictionType(SerializableEnum):
    ROOM_MEMBERSHIP = "m.room_membership"


@dataclass
class JoinRestriction(SerializableAttrs):
    type: JoinRestrictionType
    room_id: Optional[RoomID] = None


@dataclass
class JoinRulesStateEventContent(SerializableAttrs):
    join_rule: JoinRule
    allow: Optional[List[JoinRestriction]] = None


@dataclass
class RoomPinnedEventsStateEventContent(SerializableAttrs):
    pinned: List[EventID] = None


@dataclass
class RoomTombstoneStateEventContent(SerializableAttrs):
    body: str = None
    replacement_room: RoomID = None


@dataclass
class RoomEncryptionStateEventContent(SerializableAttrs):
    algorithm: EncryptionAlgorithm = None
    rotation_period_ms: int = 604800000
    rotation_period_msgs: int = 100


@dataclass
class RoomPredecessor(SerializableAttrs):
    room_id: RoomID = None
    event_id: EventID = None


@dataclass
class RoomCreateStateEventContent(SerializableAttrs):
    room_version: str = "1"
    federate: bool = field(json="m.federate", omit_default=True, default=True)
    predecessor: Optional[RoomPredecessor] = None
    type: Optional[RoomType] = None


@dataclass
class SpaceChildStateEventContent(SerializableAttrs):
    via: List[str] = None
    order: str = ""
    suggested: bool = False


@dataclass
class SpaceParentStateEventContent(SerializableAttrs):
    via: List[str] = None
    canonical: bool = False


StateEventContent = Union[
    PowerLevelStateEventContent,
    MemberStateEventContent,
    CanonicalAliasStateEventContent,
    RoomNameStateEventContent,
    RoomAvatarStateEventContent,
    RoomTopicStateEventContent,
    RoomPinnedEventsStateEventContent,
    RoomTombstoneStateEventContent,
    RoomEncryptionStateEventContent,
    RoomCreateStateEventContent,
    SpaceChildStateEventContent,
    SpaceParentStateEventContent,
    JoinRulesStateEventContent,
    Obj,
]


@dataclass
class StrippedStateUnsigned(BaseUnsigned, SerializableAttrs):
    """Unsigned information sent with state events."""

    prev_content: StateEventContent = None
    prev_sender: UserID = None
    replaces_state: EventID = None


@dataclass
class StrippedStateEvent(SerializableAttrs):
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
    def deserialize(cls, data: JSON) -> "StrippedStateEvent":
        try:
            event_type = EventType.find(data.get("type", None))
            data.get("content", {})["__mautrix_event_type"] = event_type
            data.get("unsigned", {}).get("prev_content", {})["__mautrix_event_type"] = event_type
        except ValueError:
            pass
        return super().deserialize(data)


@dataclass
class StateUnsigned(StrippedStateUnsigned, SerializableAttrs):
    invite_room_state: Optional[List[StrippedStateEvent]] = None


state_event_content_map = {
    EventType.ROOM_CREATE: RoomCreateStateEventContent,
    EventType.ROOM_POWER_LEVELS: PowerLevelStateEventContent,
    EventType.ROOM_MEMBER: MemberStateEventContent,
    EventType.ROOM_PINNED_EVENTS: RoomPinnedEventsStateEventContent,
    EventType.ROOM_CANONICAL_ALIAS: CanonicalAliasStateEventContent,
    EventType.ROOM_NAME: RoomNameStateEventContent,
    EventType.ROOM_AVATAR: RoomAvatarStateEventContent,
    EventType.ROOM_TOPIC: RoomTopicStateEventContent,
    EventType.ROOM_JOIN_RULES: JoinRulesStateEventContent,
    EventType.ROOM_TOMBSTONE: RoomTombstoneStateEventContent,
    EventType.ROOM_ENCRYPTION: RoomEncryptionStateEventContent,
    EventType.SPACE_CHILD: SpaceChildStateEventContent,
    EventType.SPACE_PARENT: SpaceParentStateEventContent,
}


@dataclass
class StateEvent(BaseRoomEvent, SerializableAttrs):
    """A room state event."""

    state_key: str
    content: StateEventContent
    unsigned: Optional[StateUnsigned] = field(factory=lambda: StateUnsigned())

    @property
    def prev_content(self) -> StateEventContent:
        if self.unsigned and self.unsigned.prev_content:
            return self.unsigned.prev_content
        return state_event_content_map.get(self.type, Obj)()

    @classmethod
    def deserialize(cls, data: JSON) -> "StateEvent":
        try:
            event_type = EventType.find(data.get("type"), t_class=EventType.Class.STATE)
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
