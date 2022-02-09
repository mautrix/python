# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging

from asyncpg import Connection

from mautrix.util.async_db.upgrade import UpgradeTable

upgrade_table = UpgradeTable(
    version_table_name="mx_version",
    database_name="matrix state cache",
    log=logging.getLogger("mau.client.db.upgrade"),
)


@upgrade_table.register(description="Latest revision", upgrades_to=2)
async def upgrade_blank_to_v2(conn: Connection, scheme: str) -> None:
    await conn.execute(
        """CREATE TABLE mx_room_state (
            room_id              TEXT PRIMARY KEY,
            is_encrypted         BOOLEAN,
            has_full_member_list BOOLEAN,
            encryption           TEXT,
            power_levels         TEXT
        )"""
    )
    if scheme != "sqlite":
        await conn.execute(
            "CREATE TYPE membership AS ENUM ('join', 'leave', 'invite', 'ban', 'knock')"
        )
    await conn.execute(
        """CREATE TABLE mx_user_profile (
            room_id     TEXT,
            user_id     TEXT,
            membership  membership NOT NULL,
            displayname TEXT,
            avatar_url  TEXT,
            PRIMARY KEY (room_id, user_id)
        )"""
    )


@upgrade_table.register(description="Stop using size-limited string fields")
async def upgrade_v2(conn: Connection, scheme: str) -> None:
    if scheme == "sqlite":
        # SQLite doesn't care about types
        return
    await conn.execute("ALTER TABLE mx_room_state ALTER COLUMN room_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN room_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN user_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN displayname TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN avatar_url TYPE TEXT")
