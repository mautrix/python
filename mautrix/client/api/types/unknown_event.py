from typing import Optional
import attr

from .serializable import SerializableAttrs
from .message_event import MessageEvent, MessageEventContent, MessageUnsigned
from .state_event import StateEvent, StateEventContent, StateUnsigned


@attr.s(auto_attribs=True)
class Unsigned(MessageUnsigned, StateUnsigned, SerializableAttrs['Unsigned']):
    pass


@attr.s(auto_attribs=True)
class EventContent(MessageEventContent, StateEventContent, SerializableAttrs['EventContent']):
    pass


@attr.s(auto_attribs=True)
class Event(MessageEvent, StateEvent, SerializableAttrs['Event']):
    content: EventContent = None
    unsigned: Optional[Unsigned] = None
