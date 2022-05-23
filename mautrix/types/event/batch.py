# Copyright (c) 2022 Tulir Asokan, Sumner Evans
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any

from attr import dataclass
import attr

from ..primitive import UserID
from ..util import SerializableAttrs
from .base import BaseEvent


@dataclass
class BatchSendEvent(BaseEvent, SerializableAttrs):
    """Base event class for events sent via a batch send request."""

    sender: UserID
    timestamp: int = attr.ib(metadata={"json": "origin_server_ts"})
    content: Any


@dataclass
class BatchSendStateEvent(BatchSendEvent, SerializableAttrs):
    """
    State events to be used as initial state events on batch send events. These never need to be
    deserialized.
    """

    state_key: str
