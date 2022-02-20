# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Optional, Union

from attr import dataclass
import attr

from .primitive import JSON, RoomID, UserID
from .util import ExtensibleEnum, SerializableAttrs, deserializer

PushRuleID = Union[RoomID, UserID, str]


class PushActionType(ExtensibleEnum):
    NOTIFY = "notify"
    DONT_NOTIFY = "dont_notify"
    COALESCE = "coalesce"


@dataclass
class PushActionDict(SerializableAttrs):
    set_tweak: Optional[str] = None
    value: Optional[str] = None


PushAction = Union[PushActionDict, PushActionType]


@deserializer(PushAction)
def deserialize_push_action(data: JSON) -> PushAction:
    if isinstance(data, str):
        return PushActionType(data)
    else:
        return PushActionDict.deserialize(data)


class PushOperator(ExtensibleEnum):
    EQUALS = "=="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="


class PushRuleScope(ExtensibleEnum):
    GLOBAL = "global"


class PushConditionKind(ExtensibleEnum):
    EVENT_MATCH = "event_match"
    CONTAINS_DISPLAY_NAME = "contains_display_name"
    ROOM_MEMBER_COUNT = "room_member_count"
    SENDER_NOTIFICATION_PERMISSION = "sender_notification_permission"


class PushRuleKind(ExtensibleEnum):
    OVERRIDE = "override"
    SENDER = "sender"
    ROOM = "room"
    CONTENT = "content"
    UNDERRIDE = "underride"


@dataclass
class PushCondition(SerializableAttrs):
    kind: PushConditionKind
    key: Optional[str] = None
    pattern: Optional[str] = None
    operator: PushOperator = attr.ib(
        default=PushOperator.EQUALS, metadata={"json": "is", "omitdefault": True}
    )


@dataclass
class PushRule(SerializableAttrs):
    rule_id: PushRuleID
    default: bool
    enabled: bool
    actions: List[PushAction]
    conditions: List[PushCondition] = attr.ib(factory=lambda: [])
    pattern: Optional[str] = None
