# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, NamedTuple
import json

from mautrix.types import (
    Member,
    Membership,
    MemberStateEventContent,
    PowerLevelStateEventContent,
    RoomEncryptionStateEventContent,
    RoomID,
    Serializable,
    UserID,
)
from mautrix.util.async_db import Database, Scheme

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

    async def get_member(self, room_id: RoomID, user_id: UserID) -> Member | None:
        res = await self.db.fetchrow(
            "SELECT membership, displayname, avatar_url "
            "FROM mx_user_profile WHERE room_id=$1 AND user_id=$2",
            room_id,
            user_id,
        )
        if res is None:
            return None
        return Member(
            membership=Membership.deserialize(res["membership"]),
            displayname=res["displayname"],
            avatar_url=res["avatar_url"],
        )

    async def set_member(
        self, room_id: RoomID, user_id: UserID, member: Member | MemberStateEventContent
    ) -> None:
        q = (
            "INSERT INTO mx_user_profile (room_id, user_id, membership, displayname, avatar_url) "
            "VALUES ($1, $2, $3, $4, $5)"
            "ON CONFLICT (room_id, user_id) DO UPDATE SET membership=$3, displayname=$4,"
            "                                             avatar_url=$5"
        )
        await self.db.execute(
            q, room_id, user_id, member.membership.value, member.displayname, member.avatar_url
        )

    async def set_membership(
        self, room_id: RoomID, user_id: UserID, membership: Membership
    ) -> None:
        q = (
            "INSERT INTO mx_user_profile (room_id, user_id, membership) VALUES ($1, $2, $3) "
            "ON CONFLICT (room_id, user_id) DO UPDATE SET membership=$3"
        )
        await self.db.execute(q, room_id, user_id, membership.value)

    async def get_members(
        self,
        room_id: RoomID,
        memberships: tuple[Membership, ...] = (Membership.JOIN, Membership.INVITE),
    ) -> list[UserID]:
        membership_values = [membership.value for membership in memberships]
        if self.db.scheme in (Scheme.POSTGRES, Scheme.COCKROACH):
            q = "SELECT user_id FROM mx_user_profile WHERE room_id=$1 AND membership=ANY($2)"
            res = await self.db.fetch(q, room_id, membership_values)
        else:
            membership_placeholders = ("?," * len(memberships)).rstrip(",")
            q = (
                "SELECT user_id FROM mx_user_profile "
                f"WHERE room_id=? AND membership IN ({membership_placeholders})"
            )
            res = await self.db.fetch(q, room_id, *membership_values)
        return [profile["user_id"] for profile in res]

    async def get_member_profiles(
        self,
        room_id: RoomID,
        memberships: tuple[Membership, ...] = (Membership.JOIN, Membership.INVITE),
    ) -> dict[UserID, Member]:
        membership_values = [membership.value for membership in memberships]
        if self.db.scheme in (Scheme.POSTGRES, Scheme.COCKROACH):
            q = (
                "SELECT user_id, membership, displayname, avatar_url FROM mx_user_profile "
                "WHERE room_id=$1 AND membership=ANY($2)"
            )
            res = await self.db.fetch(q, room_id, membership_values)
        else:
            membership_placeholders = ("?," * len(memberships)).rstrip(",")
            q = (
                "SELECT user_id, membership, displayname, avatar_url FROM mx_user_profile "
                f"WHERE room_id=? AND membership IN ({membership_placeholders})"
            )
            res = await self.db.fetch(q, room_id, *membership_values)
        return {profile["user_id"]: Member.deserialize(profile) for profile in res}

    async def get_members_filtered(
        self,
        room_id: RoomID,
        not_prefix: str,
        not_suffix: str,
        not_id: str,
        memberships: tuple[Membership, ...] = (Membership.JOIN, Membership.INVITE),
    ) -> list[UserID]:
        not_like = f"{not_prefix}%{not_suffix}"
        membership_values = [membership.value for membership in memberships]
        if self.db.scheme in (Scheme.POSTGRES, Scheme.COCKROACH):
            q = (
                "SELECT user_id FROM mx_user_profile "
                "WHERE room_id=$1 AND membership=ANY($2)"
                "AND user_id != $3 AND user_id NOT LIKE $4"
            )
            res = await self.db.fetch(q, room_id, membership_values, not_id, not_like)
        else:
            membership_placeholders = ("?," * len(memberships)).rstrip(",")
            q = (
                "SELECT user_id FROM mx_user_profile "
                f"WHERE room_id=? AND membership IN ({membership_placeholders})"
                "AND user_id != ? AND user_id NOT LIKE ?"
            )
            res = await self.db.fetch(q, room_id, *membership_values, not_id, not_like)
        return [profile["user_id"] for profile in res]

    async def set_members(
        self,
        room_id: RoomID,
        members: dict[UserID, Member | MemberStateEventContent],
        only_membership: Membership | None = None,
    ) -> None:
        columns = ["room_id", "user_id", "membership", "displayname", "avatar_url"]
        records = [
            (room_id, user_id, str(member.membership), member.displayname, member.avatar_url)
            for user_id, member in members.items()
        ]
        async with self.db.acquire() as conn, conn.transaction():
            del_q = "DELETE FROM mx_user_profile WHERE room_id=$1"
            if only_membership is None:
                await conn.execute(del_q, room_id)
            elif self.db.scheme in (Scheme.POSTGRES, Scheme.COCKROACH):
                del_q = f"{del_q} AND (membership=$2 OR user_id = ANY($3))"
                await conn.execute(del_q, room_id, only_membership.value, list(members.keys()))
            else:
                member_placeholders = ("?," * len(members)).rstrip(",")
                del_q = f"{del_q} AND (membership=? OR user_id IN ({member_placeholders}))"
                await conn.execute(del_q, room_id, only_membership.value, *members.keys())

            if self.db.scheme == Scheme.POSTGRES:
                await conn.copy_records_to_table(
                    "mx_user_profile", records=records, columns=columns
                )
            else:
                q = (
                    "INSERT INTO mx_user_profile (room_id, user_id, membership, "
                    "displayname, avatar_url) VALUES ($1, $2, $3, $4, $5)"
                )
                await conn.executemany(q, records)

            if not only_membership or only_membership == Membership.JOIN:
                await conn.execute(
                    "UPDATE mx_room_state SET has_full_member_list=true WHERE room_id=$1",
                    room_id,
                )

    async def find_shared_rooms(self, user_id: UserID) -> list[RoomID]:
        q = (
            "SELECT mx_user_profile.room_id FROM mx_user_profile "
            "LEFT JOIN mx_room_state ON mx_room_state.room_id=mx_user_profile.room_id "
            "WHERE user_id=$1 AND mx_room_state.is_encrypted=true"
        )
        rows = await self.db.fetch(q, user_id)
        return [row["room_id"] for row in rows]

    async def has_full_member_list(self, room_id: RoomID) -> bool:
        return bool(
            await self.db.fetchval(
                "SELECT has_full_member_list FROM mx_room_state WHERE room_id=$1", room_id
            )
        )

    async def has_power_levels_cached(self, room_id: RoomID) -> bool:
        return bool(
            await self.db.fetchval(
                "SELECT power_levels IS NOT NULL FROM mx_room_state WHERE room_id=$1", room_id
            )
        )

    async def get_power_levels(self, room_id: RoomID) -> PowerLevelStateEventContent | None:
        power_levels_json = await self.db.fetchval(
            "SELECT power_levels FROM mx_room_state WHERE room_id=$1", room_id
        )
        if power_levels_json is None:
            return None
        return PowerLevelStateEventContent.parse_json(power_levels_json)

    async def set_power_levels(
        self, room_id: RoomID, content: PowerLevelStateEventContent | dict[str, Any]
    ) -> None:
        await self.db.execute(
            "INSERT INTO mx_room_state (room_id, power_levels) VALUES ($1, $2) "
            "ON CONFLICT (room_id) DO UPDATE SET power_levels=$2",
            room_id,
            json.dumps(content.serialize() if isinstance(content, Serializable) else content),
        )

    async def has_encryption_info_cached(self, room_id: RoomID) -> bool:
        return bool(
            await self.db.fetchval(
                "SELECT encryption IS NULL FROM mx_room_state WHERE room_id=$1", room_id
            )
        )

    async def is_encrypted(self, room_id: RoomID) -> bool | None:
        return await self.db.fetchval(
            "SELECT is_encrypted FROM mx_room_state WHERE room_id=$1", room_id
        )

    async def get_encryption_info(self, room_id: RoomID) -> RoomEncryptionStateEventContent | None:
        row = await self.db.fetchrow(
            "SELECT is_encrypted, encryption FROM mx_room_state WHERE room_id=$1", room_id
        )
        if row is None or not row["is_encrypted"]:
            return None
        return RoomEncryptionStateEventContent.parse_json(row["encryption"])

    async def set_encryption_info(
        self, room_id: RoomID, content: RoomEncryptionStateEventContent | dict[str, Any]
    ) -> None:
        q = (
            "INSERT INTO mx_room_state (room_id, is_encrypted, encryption) VALUES ($1, true, $2) "
            "ON CONFLICT (room_id) DO UPDATE SET is_encrypted=true, encryption=$2"
        )
        await self.db.execute(
            q,
            room_id,
            json.dumps(content.serialize() if isinstance(content, Serializable) else content),
        )
