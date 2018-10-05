from typing import Optional
import attr

from ..util import SerializableAttrs
from .message import MessageEvent, MessageEventContent, MessageUnsigned
from .state import StateEvent, StateEventContent, StateUnsigned


@attr.s(auto_attribs=True)
class Unsigned(MessageUnsigned, StateUnsigned, SerializableAttrs['Unsigned']):
    """Unsigned is a combination of :MessageUnsigned: and :StateUnsigned:. As with the generic
    :Event: that uses this, this should also only be used if the type of event is not known
    beforehand."""
    pass


@attr.s(auto_attribs=True)
class EventContent(MessageEventContent, StateEventContent, SerializableAttrs['EventContent']):
    """EventContent is a combination of :MessageEventContent: and :StateEventContent:. As with the
    generic :Event: that uses this, this should also only be used if the type of event is not known
    beforehand."""
    pass


@attr.s(auto_attribs=True)
class Event(MessageEvent, StateEvent, SerializableAttrs['Event']):
    """Event is a combination of :MessageEvent: and :StateEvent:. It should only be used if the type
    of event is not known beforehand."""
    content: EventContent = None
    state_key: str = None
    unsigned: Optional[Unsigned] = None
    message_event: Optional[MessageEvent] = attr.ib(
        default=None, metadata={"flatten": True, "ignore_errors": True})
    state_event: Optional[StateEvent] = attr.ib(
        default=None, metadata={"flatten": True, "ignore_errors": True})
