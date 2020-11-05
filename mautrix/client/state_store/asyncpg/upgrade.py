# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging

from asyncpg import Connection

from mautrix.util.async_db.upgrade import UpgradeTable

upgrade_table = UpgradeTable(version_table_name="mx_version", database_name="matrix state cache",
                             log=logging.getLogger("mau.client.db.upgrade"))


@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute("""CREATE TABLE mx_room_state (
        room_id              VARCHAR(255) PRIMARY KEY,
        is_encrypted         BOOLEAN,
        has_full_member_list BOOLEAN,
        encryption           TEXT,
        power_levels         TEXT
    )""")
    await conn.execute("CREATE TYPE membership AS ENUM ('join', 'leave', 'invite', 'ban', 'knock')")
    await conn.execute("""CREATE TABLE mx_user_profile (
        room_id     VARCHAR(255),
        user_id     VARCHAR(255),
        membership  membership NOT NULL,
        displayname VARCHAR(255),
        avatar_url  VARCHAR(255),
        PRIMARY KEY (room_id, user_id)
    )""")


@upgrade_table.register(description="Stop using size-limited string fields")
async def upgrade_v2(conn: Connection) -> None:
    await conn.execute("ALTER TABLE mx_room_state ALTER COLUMN room_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN room_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN user_id TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN displayname TYPE TEXT")
    await conn.execute("ALTER TABLE mx_user_profile ALTER COLUMN avatar_url TYPE TEXT")
