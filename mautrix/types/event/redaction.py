# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional

from attr import dataclass
import attr

from ..primitive import EventID
from ..util import SerializableAttrs
from .base import BaseRoomEvent, BaseUnsigned


@dataclass
class RedactionEventContent(SerializableAttrs):
    """The content of an m.room.redaction event"""

    reason: str = None


@dataclass
class RedactionEvent(BaseRoomEvent, SerializableAttrs):
    """A m.room.redaction event"""

    content: RedactionEventContent
    redacts: EventID
    _unsigned: Optional[BaseUnsigned] = attr.ib(default=None, metadata={"json": "unsigned"})

    @property
    def unsigned(self) -> BaseUnsigned:
        if not self._unsigned:
            self._unsigned = BaseUnsigned()
        return self._unsigned

    @unsigned.setter
    def unsigned(self, value: BaseUnsigned) -> None:
        self._unsigned = value
