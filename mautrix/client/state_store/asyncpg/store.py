# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Optional, Union, NamedTuple

from mautrix.types import (Member, MemberStateEventContent, Membership, PowerLevelStateEventContent,
                           RoomEncryptionStateEventContent, RoomID, UserID)
from mautrix.util.async_db import Database

from ..abstract import StateStore
from .upgrade import upgrade_table


class RoomState(NamedTuple):
    is_encrypted: bool
    has_full_member_list: bool
    encryption: RoomEncryptionStateEventContent
    power_levels: PowerLevelStateEventContent


class PgStateStore(StateStore):
    upgrade_table = upgrade_table

    db: Database

    def __init__(self, db: Database) -> None:
        self.db = db

    async def get_member(self, room_id: RoomID, user_id: UserID) -> Optional[Member]:
        res = await self.db.fetchrow("SELECT membership, displayname, avatar_url "
                                     "FROM mx_user_profile WHERE room_id=$1 AND user_id=$2",
                                     room_id, user_id)
        if res is None:
            return None
        return Member(membership=Membership.deserialize(res["membership"]),
                      displayname=res["displayname"], avatar_url=res["avatar_url"])

    async def set_member(self, room_id: RoomID, user_id: UserID,
                         member: Union[Member, MemberStateEventContent]) -> None:
        q = ("INSERT INTO mx_user_profile (room_id, user_id, membership, displayname, avatar_url) "
             "VALUES ($1, $2, $3, $4, $5)"
             "ON CONFLICT (room_id, user_id) DO UPDATE SET membership=$3, displayname=$4,"
             "                                             avatar_url=$5")
        await self.db.execute(q, room_id, user_id, member.membership.value,
                              member.displayname, member.avatar_url)

    async def set_membership(self, room_id: RoomID, user_id: UserID,
                             membership: Membership) -> None:
        q = ("INSERT INTO mx_user_profile (room_id, user_id, membership) VALUES ($1, $2, $3) "
             "ON CONFLICT (room_id, user_id) DO UPDATE SET membership=$3")
        await self.db.execute(q, room_id, user_id, membership.value)

    async def get_members(self, room_id: RoomID) -> Optional[List[UserID]]:
        res = await self.db.fetch("SELECT user_id FROM mx_user_profile "
                                  "WHERE room_id=$1 AND (membership='join' OR membership='invite')",
                                  room_id)
        return [profile["user_id"] for profile in res]

    async def get_members_filtered(self, room_id: RoomID, not_prefix: str, not_suffix: str,
                                   not_id: str) -> Optional[List[UserID]]:
        res = await self.db.fetch("SELECT user_id FROM mx_user_profile "
                                  "WHERE room_id=$1 AND (membership='join' OR membership='invite')"
                                  "AND user_id != $2 AND user_id NOT LIKE $3",
                                  room_id, not_id, f"{not_prefix}%{not_suffix}")
        return [profile["user_id"] for profile in res]

    async def set_members(self, room_id: RoomID,
                          members: Dict[UserID, Union[Member, MemberStateEventContent]]) -> None:
        columns = ["room_id", "user_id", "membership", "displayname", "avatar_url"]
        records = [(room_id, user_id, str(member.membership), member.displayname, member.avatar_url)
                   for user_id, member in members.items()]
        async with self.db.acquire() as conn, conn.transaction():
            del_q = "DELETE FROM mx_user_profile WHERE room_id=$1"
            await conn.execute(del_q, room_id)
            await conn.copy_records_to_table("mx_user_profile", records=records, columns=columns)

    async def has_full_member_list(self, room_id: RoomID) -> bool:
        return bool(await self.db.fetchval("SELECT has_full_member_list FROM mx_room_state "
                                           "WHERE room_id=$1", room_id))

    async def has_power_levels_cached(self, room_id: RoomID) -> bool:
        return bool(await self.db.fetchval("SELECT power_levels IS NULL FROM mx_room_state "
                                           "WHERE room_id=$1", room_id))

    async def get_power_levels(self, room_id: RoomID) -> Optional[PowerLevelStateEventContent]:
        power_levels_json = await self.db.fetchval("SELECT power_levels FROM mx_room_state "
                                                   "WHERE room_id=$1", room_id)
        if power_levels_json is None:
            return None
        return PowerLevelStateEventContent.parse_json(power_levels_json)

    async def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent) -> None:
        await self.db.execute("INSERT INTO mx_room_state (room_id, power_levels) VALUES ($1, $2) "
                              "ON CONFLICT (room_id) DO UPDATE SET power_levels=$2",
                              room_id, content.json())

    async def has_encryption_info_cached(self, room_id: RoomID) -> bool:
        return bool(await self.db.fetchval("SELECT encryption IS NULL FROM mx_room_state "
                                           "WHERE room_id=$1", room_id))

    async def is_encrypted(self, room_id: RoomID) -> Optional[bool]:
        return await self.db.fetchval("SELECT is_encrypted FROM mx_room_state WHERE room_id=$1",
                                      room_id)

    async def get_encryption_info(self, room_id: RoomID
                                  ) -> Optional[RoomEncryptionStateEventContent]:
        row = await self.db.fetchrow("SELECT is_encrypted, encryption FROM mx_room_state "
                                     "WHERE room_id=$1", room_id)
        if row is None or not row["is_encrypted"]:
            return None
        return RoomEncryptionStateEventContent.parse_json(row["encryption"])

    async def set_encryption_info(self, room_id: RoomID,
                                  content: RoomEncryptionStateEventContent) -> None:
        q = ("INSERT INTO mx_room_state (room_id, is_encrypted, encryption) VALUES ($1, true, $2) "
             "ON CONFLICT (room_id) DO UPDATE SET is_encrypted=true, encryption=$2")
        await self.db.execute(q, room_id, content.json())
