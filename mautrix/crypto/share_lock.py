# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict
import asyncio

from mautrix.types import RoomID


class ShareSessionLock:
    loop: asyncio.AbstractEventLoop
    _share_session_waiters: Dict[RoomID, asyncio.Future]

    def __init__(self) -> None:
        self._share_session_waiters = {}

    async def share_session_lock(self, room_id: RoomID) -> bool:
        try:
            waiter = self._share_session_waiters[room_id]
        except KeyError:
            self._share_session_waiters[room_id] = self.loop.create_future()
            return True
        else:
            await waiter
            return False

    def share_session_unlock(self, room_id: RoomID) -> None:
        try:
            self._share_session_waiters[room_id].set_result(None)
            del self._share_session_waiters[room_id]
        except KeyError:
            pass
