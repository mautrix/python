from typing import Dict
import attr

from ..util import SerializableAttrs
from .base import BaseEvent


@attr.s(auto_attribs=True)
class RoomTagInfo(SerializableAttrs['RoomTagInfo']):
    order: int = None


@attr.s(auto_attribs=True)
class AccountDataEventContent(SerializableAttrs['AccountDataEventContent']):
    room_tags: Dict[str, RoomTagInfo] = attr.ib(default=None, metadata={"json": "tags"})


@attr.s(auto_attribs=True)
class AccountDataEvent(BaseEvent, SerializableAttrs['AccountDataEvent']):
    content: AccountDataEventContent = None
