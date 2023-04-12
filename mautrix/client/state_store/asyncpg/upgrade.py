# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging

from mautrix.util.async_db import Connection, Scheme, UpgradeTable

upgrade_table = UpgradeTable(
    version_table_name="mx_version",
    database_name="matrix state cache",
    log=logging.getLogger("mau.client.db.upgrade"),
)


@upgrade_table.register(description="Latest revision", upgrades_to=3)
async def upgrade_blank_to_v3(conn: Connection, scheme: Scheme) -> None:
    await conn.execute(
        """CREATE TABLE mx_room_state (
            room_id              TEXT PRIMARY KEY,
            is_encrypted         BOOLEAN,
            has_full_member_list BOOLEAN,
            encryption           TEXT,
            power_levels         TEXT
        )"""
    )
    membership_check = ""
    if scheme != Scheme.SQLITE:
        await conn.execute(
            "CREATE TYPE membership AS ENUM ('join', 'leave', 'invite', 'ban', 'knock')"
        )
    else:
        membership_check = "CHECK (membership IN ('join', 'leave', 'invite', 'ban', 'knock'))"
    await conn.execute(
        f"""CREATE TABLE mx_user_profile (
            room_id     TEXT,
            user_id     TEXT,
            membership  membership NOT NULL {membership_check},
            displayname TEXT,
            avatar_url  TEXT,
            PRIMARY KEY (room_id, user_id)
        )"""
    )


@upgrade_table.register(description="Stop using size-limited string fields")
async def upgrade_v2(conn: Connection, scheme: Scheme) -> None:
    if scheme == Scheme.SQLITE:
        # SQLite doesn't care about types
        return
    await conn.execute("ALTER TABLE mx_room_state ALTER COLUMN room_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN room_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN user_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN displayname TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN avatar_url TYPE TEXT")


@upgrade_table.register(description="Mark rooms that need crypto state event resynced")
async def upgrade_v3(conn: Connection) -> None:
    if await conn.table_exists("portal"):
        await conn.execute(
            """
            INSERT INTO mx_room_state (room_id, encryption)
            SELECT portal.mxid, '{"resync":true}' FROM portal
                WHERE portal.encrypted=true AND portal.mxid IS NOT NULL
            ON CONFLICT (room_id) DO UPDATE
                SET encryption=excluded.encryption
                WHERE mx_room_state.encryption IS NULL
            """
        )
