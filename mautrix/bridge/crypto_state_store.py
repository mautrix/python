# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Awaitable, Callable
from abc import ABC

from mautrix import __optional_imports__
from mautrix.bridge.portal import BasePortal
from mautrix.crypto import StateStore
from mautrix.types import RoomEncryptionStateEventContent, RoomID, UserID
from mautrix.util.async_db import Database

GetPortalFunc = Callable[[RoomID], Awaitable[BasePortal]]


class BaseCryptoStateStore(StateStore, ABC):
    get_portal: GetPortalFunc

    def __init__(self, get_portal: GetPortalFunc):
        self.get_portal = get_portal

    async def is_encrypted(self, room_id: RoomID) -> bool:
        portal = await self.get_portal(room_id)
        return portal.encrypted if portal else False


try:
    from mautrix.client.state_store.sqlalchemy import RoomState, UserProfile

    class SQLCryptoStateStore(BaseCryptoStateStore):
        @staticmethod
        async def find_shared_rooms(user_id: UserID) -> list[RoomID]:
            return [profile.room_id for profile in UserProfile.find_rooms_with_user(user_id)]

        @staticmethod
        async def get_encryption_info(room_id: RoomID) -> RoomEncryptionStateEventContent | None:
            state = RoomState.get(room_id)
            if not state:
                return None
            return state.encryption

except ImportError:
    if __optional_imports__:
        raise
    UserProfile = None
    RoomState = None
    SQLCryptoStateStore = None


class PgCryptoStateStore(BaseCryptoStateStore):
    db: Database

    def __init__(self, db: Database, get_portal: GetPortalFunc) -> None:
        super().__init__(get_portal)
        self.db = db

    async def find_shared_rooms(self, user_id: UserID) -> list[RoomID]:
        rows = await self.db.fetch(
            "SELECT room_id FROM mx_user_profile "
            "LEFT JOIN portal ON portal.mxid=mx_user_profile.room_id "
            "WHERE user_id=$1 AND portal.encrypted=true",
            user_id,
        )
        return [row["room_id"] for row in rows]

    async def get_encryption_info(self, room_id: RoomID) -> RoomEncryptionStateEventContent | None:
        val = await self.db.fetchval(
            "SELECT encryption FROM mx_room_state WHERE room_id=$1", room_id
        )
        if not val:
            return None
        return RoomEncryptionStateEventContent.parse_json(val)
