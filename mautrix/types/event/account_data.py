# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import TYPE_CHECKING, Dict, List, Union

from attr import dataclass
import attr

from ..primitive import JSON, RoomID, UserID
from ..util import Obj, SerializableAttrs, deserializer
from .base import BaseEvent, EventType

if TYPE_CHECKING:
    from mautrix.crypto.ssss import EncryptedAccountDataEventContent, KeyMetadata


@dataclass
class RoomTagInfo(SerializableAttrs):
    order: Union[int, float, str] = None


@dataclass
class RoomTagAccountDataEventContent(SerializableAttrs):
    tags: Dict[str, RoomTagInfo] = attr.ib(default=None, metadata={"json": "tags"})


@dataclass
class SecretStorageDefaultKeyEventContent(SerializableAttrs):
    key: str


DirectAccountDataEventContent = Dict[UserID, List[RoomID]]

AccountDataEventContent = Union[
    RoomTagAccountDataEventContent,
    DirectAccountDataEventContent,
    SecretStorageDefaultKeyEventContent,
    "EncryptedAccountDataEventContent",
    "KeyMetadata",
    Obj,
]
account_data_event_content_map = {
    EventType.TAG: RoomTagAccountDataEventContent,
    EventType.SECRET_STORAGE_DEFAULT_KEY: SecretStorageDefaultKeyEventContent,
    # m.direct doesn't really need deserializing
    # EventType.DIRECT: DirectAccountDataEventContent,
}


# TODO remaining account data event types


@dataclass
class AccountDataEvent(BaseEvent, SerializableAttrs):
    content: AccountDataEventContent

    @classmethod
    def deserialize(cls, data: JSON) -> "AccountDataEvent":
        try:
            evt_type = EventType.find(data.get("type"))
            data.get("content", {})["__mautrix_event_type"] = evt_type
        except ValueError:
            return Obj(**data)
        evt = super().deserialize(data)
        evt.type = evt_type
        return evt

    @staticmethod
    @deserializer(AccountDataEventContent)
    def deserialize_content(data: JSON) -> AccountDataEventContent:
        evt_type = data.pop("__mautrix_event_type", None)
        content_type = account_data_event_content_map.get(evt_type, None)
        if not content_type:
            return Obj(**data)
        return content_type.deserialize(data)
