# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, Optional, TYPE_CHECKING

from mautrix.types import (RoomID, UserID, Member, Membership, PowerLevelStateEventContent,
                           RoomEncryptionStateEventContent, MemberStateEventContent)
from mautrix.util.file_store import FileStore

from .memory import MemoryStateStore

if TYPE_CHECKING:
    from mautrix.util.file_store import PathLike, Filer


class FileStateStore(FileStore, MemoryStateStore):
    def __init__(self, path: 'PathLike', filer: Optional['Filer'] = None, binary: bool = True,
                 save_interval: float = 60.0) -> None:
        FileStore.__init__(self, path, filer, binary, save_interval)
        MemoryStateStore.__init__(self)

    async def set_membership(self, room_id: RoomID, user_id: UserID,
                             membership: Membership) -> None:
        await super().set_membership(room_id, user_id, membership)
        self._time_limited_flush()

    async def set_member(self, room_id: RoomID, user_id: UserID,
                         member: Union[Member, MemberStateEventContent]) -> None:
        await super().set_member(room_id, user_id, member)
        self._time_limited_flush()

    async def set_encryption_info(self, room_id: RoomID,
                                  content: RoomEncryptionStateEventContent) -> None:
        await super().set_encryption_info(room_id, content)
        self._time_limited_flush()

    async def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent) -> None:
        await super().set_power_levels(room_id, content)
        self._time_limited_flush()
