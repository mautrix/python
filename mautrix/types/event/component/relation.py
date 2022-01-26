# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Optional

from attr import dataclass

from ...primitive import EventID
from ...util import ExtensibleEnum, SerializableAttrs, field


class RelationType(ExtensibleEnum):
    ANNOTATION: "RelationType" = "m.annotation"
    REFERENCE: "RelationType" = "m.reference"
    REPLACE: "RelationType" = "m.replace"
    THREAD: "RelationType" = "m.thread"


@dataclass
class InReplyTo(SerializableAttrs):
    event_id: EventID
    render_in: Optional[List[RelationType]] = None


@dataclass
class RelatesTo(SerializableAttrs):
    rel_type: Optional[RelationType] = None
    event_id: Optional[EventID] = None
    key: Optional[str] = None

    in_reply_to_: Optional[InReplyTo] = field(default=None, json="m.in_reply_to")

    @property
    def reply_to(self) -> Optional[EventID]:
        if self.in_reply_to_:
            return self.in_reply_to_.event_id
        return None

    @reply_to.setter
    def reply_to(self, val: Optional[EventID]) -> None:
        self.in_reply_to_ = InReplyTo(event_id=val) if val else None
