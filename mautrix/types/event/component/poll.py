# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List

from attr import dataclass

from ...util import ExtensibleEnum, SerializableAttrs
from .text import Message


class PollKind(ExtensibleEnum):
    DISCLOSED = "org.matrix.msc3381.poll.disclosed"
    UNDISCLOSED = "org.matrix.msc3381.poll.undisclosed"


@dataclass
class PollAnswer(Message, SerializableAttrs):
    id: str


@dataclass
class PollStart(SerializableAttrs):
    question: Message
    kind: PollKind
    answers: List[PollAnswer]


@dataclass
class PollResponse(SerializableAttrs):
    answers: List[str]
