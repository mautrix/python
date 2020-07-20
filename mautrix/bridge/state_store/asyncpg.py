# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Callable, Union, Awaitable

from mautrix.types import UserID
from mautrix.appservice.state_store.asyncpg import PgASStateStore
from mautrix.util.async_db import Database

from ..puppet import BasePuppet

GetPuppetFunc = Union[Callable[[UserID], Awaitable[BasePuppet]],
                      Callable[[UserID, bool], Awaitable[BasePuppet]]]


class PgBridgeStateStore(PgASStateStore):
    def __init__(self, db: Database, get_puppet: 'GetPuppetFunc',
                 get_double_puppet: 'GetPuppetFunc') -> None:
        super().__init__(db)
        self.get_puppet = get_puppet
        self.get_double_puppet = get_double_puppet

    async def is_registered(self, user_id: UserID) -> bool:
        puppet = await self.get_puppet(user_id)
        if puppet:
            return puppet.is_registered
        custom_puppet = await self.get_double_puppet(user_id)
        if custom_puppet:
            return True
        return await super().is_registered(user_id)

    async def registered(self, user_id: UserID) -> None:
        puppet = await self.get_puppet(user_id, True)
        if puppet:
            puppet.is_registered = True
            await puppet.save()
        else:
            await super().registered(user_id)
