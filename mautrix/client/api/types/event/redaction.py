from typing import Optional
from attr import dataclass

from ..util import SerializableAttrs
from .base import BaseRoomEvent, BaseUnsigned


@dataclass
class RedactionEventContent(SerializableAttrs['RedactionEventContent']):
    """The content of an m.room.redaction event"""
    reason: str = None


@dataclass
class RedactionEvent(BaseRoomEvent, SerializableAttrs['RedactionEvent']):
    """A m.room.redaction event"""
    content: RedactionEventContent
    redacts: str
    _unsigned: Optional[BaseUnsigned] = None

    @property
    def unsigned(self) -> BaseUnsigned:
        if not self._unsigned:
            self._unsigned = BaseUnsigned()
        return self._unsigned

    @unsigned.setter
    def unsigned(self, value: BaseUnsigned) -> None:
        self._unsigned = value
