# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional

from attr import dataclass

from ...primitive import EventID
from ...util import SerializableAttrs, field
from .relation import RelatesTo, RelationType


@dataclass
class BaseExtensibleContent(SerializableAttrs):
    _relates_to: Optional[RelatesTo] = field(default=None, json="m.relates_to")

    @property
    def relates_to(self) -> RelatesTo:
        if not self._relates_to:
            self._relates_to = RelatesTo()
        return self._relates_to

    @relates_to.setter
    def relates_to(self, val: RelatesTo) -> None:
        self._relates_to = val
