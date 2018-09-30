from typing import Optional
import attr

from ..util import SerializableAttrs
from .message import MessageEvent, MessageEventContent, MessageUnsigned
from .state import StateEvent, StateEventContent, StateUnsigned


@attr.s(auto_attribs=True)
class Unsigned(MessageUnsigned, StateUnsigned, SerializableAttrs['Unsigned']):
    pass


@attr.s(auto_attribs=True)
class EventContent(MessageEventContent, StateEventContent, SerializableAttrs['EventContent']):
    pass


@attr.s(auto_attribs=True)
class Event(MessageEvent, StateEvent, SerializableAttrs['Event']):
    content: EventContent = None
    state_key: str = None
    unsigned: Optional[Unsigned] = None
