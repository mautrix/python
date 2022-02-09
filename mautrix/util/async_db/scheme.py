# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from enum import Enum


class Scheme(Enum):
    POSTGRES = "postgres"
    COCKROACH = "cockroach"
    SQLITE = "sqlite"

    def __eq__(self, other: Scheme | str) -> bool:
        if isinstance(other, str):
            return self.value == other
        else:
            return super().__eq__(other)
