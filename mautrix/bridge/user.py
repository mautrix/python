# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any
from abc import ABC, abstractmethod

from mautrix.types import UserID


class BaseUser(ABC):
    is_whitelisted: bool
    mxid: UserID
    command_status: Dict[str, Any]

    @classmethod
    @abstractmethod
    def get_by_mxid(cls, mxid: UserID) -> 'BaseUser':
        pass

    @abstractmethod
    async def is_logged_in(self) -> bool:
        pass
