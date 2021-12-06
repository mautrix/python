# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, ClassVar, Optional

from mautrix.types import JSON, ExtensibleEnum, Serializable, SerializableEnum

class RoomType(ExtensibleEnum):
    SPACE: "RoomType"

class EventType(Serializable):
    class Class(SerializableEnum):
        UNKNOWN = "unknown"
        STATE = "state"
        MESSAGE = "message"
        ACCOUNT_DATA = "account_data"
        EPHEMERAL = "ephemeral"
        TO_DEVICE = "to_device"
    _by_event_type: ClassVar[dict[str, EventType]]

    ROOM_CANONICAL_ALIAS: "EventType"
    ROOM_CREATE: "EventType"
    ROOM_JOIN_RULES: "EventType"
    ROOM_MEMBER: "EventType"
    ROOM_POWER_LEVELS: "EventType"
    ROOM_HISTORY_VISIBILITY: "EventType"
    ROOM_NAME: "EventType"
    ROOM_TOPIC: "EventType"
    ROOM_AVATAR: "EventType"
    ROOM_PINNED_EVENTS: "EventType"
    ROOM_TOMBSTONE: "EventType"
    ROOM_ENCRYPTION: "EventType"

    SPACE_CHILD: "EventType"
    SPACE_PARENT: "EventType"

    ROOM_REDACTION: "EventType"
    ROOM_MESSAGE: "EventType"
    ROOM_ENCRYPTED: "EventType"
    STICKER: "EventType"
    REACTION: "EventType"

    CALL_INVITE: "EventType"
    CALL_CANDIDATES: "EventType"
    CALL_SELECT_ANSWER: "EventType"
    CALL_ANSWER: "EventType"
    CALL_HANGUP: "EventType"
    CALL_REJECT: "EventType"
    CALL_NEGOTIATE: "EventType"

    RECEIPT: "EventType"
    TYPING: "EventType"
    PRESENCE: "EventType"

    DIRECT: "EventType"
    PUSH_RULES: "EventType"
    TAG: "EventType"
    IGNORED_USER_LIST: "EventType"

    TO_DEVICE_ENCRYPTED: "EventType"
    TO_DEVICE_DUMMY: "EventType"
    ROOM_KEY: "EventType"
    ROOM_KEY_WITHHELD: "EventType"
    ORG_MATRIX_ROOM_KEY_WITHHELD: "EventType"
    ROOM_KEY_REQUEST: "EventType"
    FORWARDED_ROOM_KEY: "EventType"

    ALL: "EventType"

    is_message: bool
    is_state: bool
    is_ephemeral: bool
    is_account_data: bool
    is_to_device: bool

    t: str
    t_class: Class
    def __init__(self, t: str, t_class: Class) -> None: ...
    @classmethod
    def find(cls, t: str, t_class: Optional[Class] = None) -> "EventType": ...
    def serialize(self) -> JSON: ...
    @classmethod
    def deserialize(cls, raw: JSON) -> Any: ...
    def with_class(self, t_class: Class) -> "EventType": ...
