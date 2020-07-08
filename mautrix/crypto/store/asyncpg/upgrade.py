# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging

from asyncpg import Connection

from mautrix.util.async_db.upgrade import UpgradeTable
from mautrix.util.logging import TraceLogger

upgrade_table = UpgradeTable(version_table_name="crypto_version",
                             log=logging.getLogger("mau.crypto.db.upgrade"))


@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute("""CREATE TABLE IF NOT EXISTS crypto_account (
        device_id  VARCHAR(255) PRIMARY KEY,
        shared     BOOLEAN      NOT NULL,
        sync_token TEXT         NOT NULL,
        account    bytea        NOT NULL
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS crypto_message_index (
        sender_key CHAR(43),
        session_id CHAR(43),
        "index"    INTEGER,
        event_id   VARCHAR(255) NOT NULL,
        timestamp  BIGINT       NOT NULL,
        PRIMARY KEY (sender_key, session_id, "index")
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS crypto_tracked_user (
        user_id VARCHAR(255) PRIMARY KEY
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS crypto_device (
        user_id      VARCHAR(255),
        device_id    VARCHAR(255),
        identity_key CHAR(43)      NOT NULL,
        signing_key  CHAR(43)      NOT NULL,
        trust        SMALLINT      NOT NULL,
        deleted      BOOLEAN       NOT NULL,
        name         VARCHAR(255)  NOT NULL,
        PRIMARY KEY (user_id, device_id)
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS crypto_olm_session (
        session_id   CHAR(43)  PRIMARY KEY,
        sender_key   CHAR(43)  NOT NULL,
        session      bytea     NOT NULL,
        created_at   timestamp NOT NULL,
        last_used    timestamp NOT NULL
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS crypto_megolm_inbound_session (
        session_id   CHAR(43)     PRIMARY KEY,
        sender_key   CHAR(43)     NOT NULL,
        signing_key  CHAR(43)     NOT NULL,
        room_id      VARCHAR(255) NOT NULL,
        session      bytea        NOT NULL,
        forwarding_chains TEXT    NOT NULL
    )""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS crypto_megolm_outbound_session (
        room_id       VARCHAR(255) PRIMARY KEY,
        session_id    CHAR(43)     NOT NULL UNIQUE,
        session       bytea        NOT NULL,
        shared        BOOLEAN      NOT NULL,
        max_messages  INTEGER      NOT NULL,
        message_count INTEGER      NOT NULL,
        max_age       INTERVAL     NOT NULL,
        created_at    timestamp    NOT NULL,
        last_used     timestamp    NOT NULL
    )""")
