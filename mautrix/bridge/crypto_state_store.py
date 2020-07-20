# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Callable, Awaitable, Optional
from abc import ABC

from mautrix.types import RoomID, UserID, RoomEncryptionStateEventContent
from mautrix.crypto import StateStore

from mautrix.bridge.portal import BasePortal

GetPortalFunc = Callable[[RoomID], Awaitable[BasePortal]]


class BaseCryptoStateStore(StateStore, ABC):
    get_portal: GetPortalFunc

    def __init__(self, get_portal: GetPortalFunc):
        self.get_portal = get_portal

    async def is_encrypted(self, room_id: RoomID) -> bool:
        portal = await self.get_portal(room_id)
        return portal.encrypted if portal else False


try:
    from mautrix.client.state_store.sqlalchemy import UserProfile, RoomState


    class SQLCryptoStateStore(BaseCryptoStateStore):
        @staticmethod
        async def find_shared_rooms(user_id: UserID) -> List[RoomID]:
            return [profile.user_id for profile in UserProfile.find_rooms_with_user(user_id)]

        @staticmethod
        async def get_encryption_info(room_id: RoomID) -> Optional[RoomEncryptionStateEventContent]:
            state = RoomState.get(room_id)
            if not state:
                return None
            return state.encryption
except ImportError:
    UserProfile = None
    RoomState = None
    SQLCryptoStateStore = None

try:
    from mautrix.util.async_db import Database


    class PgCryptoStateStore(BaseCryptoStateStore):
        db: Database

        def __init__(self, db: Database, get_portal: GetPortalFunc) -> None:
            super().__init__(get_portal)
            self.db = db

        async def find_shared_rooms(self, user_id: UserID) -> List[RoomID]:
            rows = await self.db.fetch("SELECT room_id FROM mx_user_profile "
                                       "LEFT JOIN portal ON portal.mxid=mx_user_profile.room_id "
                                       "WHERE user_id=$1 AND portal.encrypted=true", user_id)
            return [row["room_id"] for row in rows]

        async def get_encryption_info(self, room_id: RoomID
                                      ) -> Optional[RoomEncryptionStateEventContent]:
            val = await self.db.fetchval("SELECT encryption FROM mx_room_state WHERE room_id=$1",
                                         room_id)
            if not val:
                return None
            return RoomEncryptionStateEventContent.parse_json(val)
except ImportError:
    Database = None
    PgStateStore = None
