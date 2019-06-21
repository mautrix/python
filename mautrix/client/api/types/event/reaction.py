# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
from attr import dataclass
import attr

from ..util import SerializableAttrs
from .base import BaseRoomEvent, BaseUnsigned
from .message import RelatesTo


@dataclass
class ReactionEventContent(SerializableAttrs['ReactionEventContent']):
    """The content of an m.reaction event"""
    relates_to: RelatesTo


@dataclass
class ReactionEvent(BaseRoomEvent, SerializableAttrs['ReactionEvent']):
    """A m.reaction event"""
    content: ReactionEventContent
    _unsigned: Optional[BaseUnsigned] = attr.ib(default=None, metadata={"json": "unsigned"})

    @property
    def unsigned(self) -> BaseUnsigned:
        if not self._unsigned:
            self._unsigned = BaseUnsigned()
        return self._unsigned

    @unsigned.setter
    def unsigned(self, value: BaseUnsigned) -> None:
        self._unsigned = value
