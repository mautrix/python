# Copyright (c) 2023 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import logging

from mautrix.util.async_db import Connection, Scheme, UpgradeTable

upgrade_table = UpgradeTable(
    version_table_name="crypto_version",
    database_name="crypto store",
    log=logging.getLogger("mau.crypto.db.upgrade"),
)


@upgrade_table.register(description="Latest revision", upgrades_to=10)
async def upgrade_blank_to_latest(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS crypto_account (
            account_id TEXT    PRIMARY KEY,
            device_id  TEXT    NOT NULL,
            shared     BOOLEAN NOT NULL,
            sync_token TEXT    NOT NULL,
            account    bytea   NOT NULL
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS crypto_message_index (
            sender_key CHAR(43),
            session_id CHAR(43),
            "index"    INTEGER,
            event_id   TEXT   NOT NULL,
            timestamp  BIGINT NOT NULL,
            PRIMARY KEY (sender_key, session_id, "index")
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS crypto_tracked_user (
            user_id TEXT PRIMARY KEY
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS crypto_device (
            user_id      TEXT,
            device_id    TEXT,
            identity_key CHAR(43) NOT NULL,
            signing_key  CHAR(43) NOT NULL,
            trust        SMALLINT NOT NULL,
            deleted      BOOLEAN  NOT NULL,
            name         TEXT     NOT NULL,
            PRIMARY KEY (user_id, device_id)
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS crypto_olm_session (
            account_id     TEXT,
            session_id     CHAR(43),
            sender_key     CHAR(43)  NOT NULL,
            session        bytea     NOT NULL,
            created_at     timestamp NOT NULL,
            last_decrypted timestamp NOT NULL,
            last_encrypted timestamp NOT NULL,
            PRIMARY KEY (account_id, session_id)
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS crypto_megolm_inbound_session (
            account_id        TEXT,
            session_id        CHAR(43),
            sender_key        CHAR(43)  NOT NULL,
            signing_key       CHAR(43),
            room_id           TEXT      NOT NULL,
            session           bytea,
            forwarding_chains TEXT,
            withheld_code     TEXT,
            withheld_reason   TEXT,
            ratchet_safety    jsonb,
            received_at       timestamp,
            max_age           BIGINT,
            max_messages      INTEGER,
            is_scheduled      BOOLEAN NOT NULL DEFAULT false,
            PRIMARY KEY (account_id, session_id)
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS crypto_megolm_outbound_session (
            account_id    TEXT,
            room_id       TEXT,
            session_id    CHAR(43)  NOT NULL UNIQUE,
            session       bytea     NOT NULL,
            shared        BOOLEAN   NOT NULL,
            max_messages  INTEGER   NOT NULL,
            message_count INTEGER   NOT NULL,
            max_age       BIGINT    NOT NULL,
            created_at    timestamp NOT NULL,
            last_used     timestamp NOT NULL,
            PRIMARY KEY (account_id, room_id)
        )"""
    )
    await conn.execute(
        """CREATE TABLE crypto_cross_signing_keys (
            user_id TEXT,
            usage   TEXT,
            key     CHAR(43) NOT NULL,

            first_seen_key CHAR(43) NOT NULL,

            PRIMARY KEY (user_id, usage)
        )"""
    )
    await conn.execute(
        """CREATE TABLE crypto_cross_signing_signatures (
            signed_user_id TEXT,
            signed_key     TEXT,
            signer_user_id TEXT,
            signer_key     TEXT,
            signature      CHAR(88) NOT NULL,
            PRIMARY KEY (signed_user_id, signed_key, signer_user_id, signer_key)
        )"""
    )


@upgrade_table.register(description="Add account_id primary key column")
async def upgrade_v2(conn: Connection, scheme: Scheme) -> None:
    if scheme == Scheme.SQLITE:
        await conn.execute("DROP TABLE crypto_account")
        await conn.execute("DROP TABLE crypto_olm_session")
        await conn.execute("DROP TABLE crypto_megolm_inbound_session")
        await conn.execute("DROP TABLE crypto_megolm_outbound_session")
        await conn.execute(
            """CREATE TABLE crypto_account (
                account_id VARCHAR(255) PRIMARY KEY,
                device_id  VARCHAR(255) NOT NULL,
                shared     BOOLEAN      NOT NULL,
                sync_token TEXT         NOT NULL,
                account    bytea        NOT NULL
            )"""
        )
        await conn.execute(
            """CREATE TABLE crypto_olm_session (
                account_id   VARCHAR(255),
                session_id   CHAR(43),
                sender_key   CHAR(43)  NOT NULL,
                session      bytea     NOT NULL,
                created_at   timestamp NOT NULL,
                last_used    timestamp NOT NULL,
                PRIMARY KEY (account_id, session_id)
            )"""
        )
        await conn.execute(
            """CREATE TABLE crypto_megolm_inbound_session (
                account_id   VARCHAR(255),
                session_id   CHAR(43),
                sender_key   CHAR(43)     NOT NULL,
                signing_key  CHAR(43)     NOT NULL,
                room_id      VARCHAR(255) NOT NULL,
                session      bytea        NOT NULL,
                forwarding_chains TEXT    NOT NULL,
                PRIMARY KEY (account_id, session_id)
            )"""
        )
        await conn.execute(
            """CREATE TABLE crypto_megolm_outbound_session (
                account_id    VARCHAR(255),
                room_id       VARCHAR(255),
                session_id    CHAR(43)     NOT NULL UNIQUE,
                session       bytea        NOT NULL,
                shared        BOOLEAN      NOT NULL,
                max_messages  INTEGER      NOT NULL,
                message_count INTEGER      NOT NULL,
                max_age       BIGINT       NOT NULL,
                created_at    timestamp    NOT NULL,
                last_used     timestamp    NOT NULL,
                PRIMARY KEY (account_id, room_id)
            )"""
        )
    else:

        async def add_account_id_column(table: str, pkey_columns: list[str]) -> None:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN account_id VARCHAR(255)")
            await conn.execute(f"UPDATE {table} SET account_id=''")
            await conn.execute(f"ALTER TABLE {table} ALTER COLUMN account_id SET NOT NULL")
            await conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
            pkey_columns.append("account_id")
            pkey_columns_str = ", ".join(f'"{col}"' for col in pkey_columns)
            await conn.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
                f"PRIMARY KEY ({pkey_columns_str})"
            )

        await add_account_id_column("crypto_account", [])
        await add_account_id_column("crypto_olm_session", ["session_id"])
        await add_account_id_column("crypto_megolm_inbound_session", ["session_id"])
        await add_account_id_column("crypto_megolm_outbound_session", ["room_id"])


@upgrade_table.register(description="Stop using size-limited string fields")
async def upgrade_v3(conn: Connection, scheme: Scheme) -> None:
    if scheme == Scheme.SQLITE:
        return
    await conn.execute("ALTER TABLE crypto_account ALTER COLUMN account_id TYPE TEXT")
    await conn.execute("ALTER TABLE crypto_account ALTER COLUMN device_id TYPE TEXT")
    await conn.execute("ALTER TABLE crypto_message_index ALTER COLUMN event_id TYPE TEXT")
    await conn.execute("ALTER TABLE crypto_tracked_user ALTER COLUMN user_id TYPE TEXT")
    await conn.execute("ALTER TABLE crypto_device ALTER COLUMN user_id TYPE TEXT")
    await conn.execute("ALTER TABLE crypto_device ALTER COLUMN device_id TYPE TEXT")
    await conn.execute("ALTER TABLE crypto_device ALTER COLUMN name TYPE TEXT")
    await conn.execute("ALTER TABLE crypto_olm_session ALTER COLUMN account_id TYPE TEXT")
    await conn.execute(
        "ALTER TABLE crypto_megolm_inbound_session ALTER COLUMN account_id TYPE TEXT"
    )
    await conn.execute("ALTER TABLE crypto_megolm_inbound_session ALTER COLUMN room_id TYPE TEXT")
    await conn.execute(
        "ALTER TABLE crypto_megolm_outbound_session ALTER COLUMN account_id TYPE TEXT"
    )
    await conn.execute("ALTER TABLE crypto_megolm_outbound_session ALTER COLUMN room_id TYPE TEXT")


@upgrade_table.register(description="Split last_used into last_encrypted and last_decrypted")
async def upgrade_v4(conn: Connection, scheme: Scheme) -> None:
    await conn.execute("ALTER TABLE crypto_olm_session RENAME COLUMN last_used TO last_decrypted")
    await conn.execute("ALTER TABLE crypto_olm_session ADD COLUMN last_encrypted timestamp")
    await conn.execute("UPDATE crypto_olm_session SET last_encrypted=last_decrypted")
    if scheme == Scheme.POSTGRES:
        # This is too hard to do on sqlite, so let's just do it on postgres
        await conn.execute(
            "ALTER TABLE crypto_olm_session ALTER COLUMN last_encrypted SET NOT NULL"
        )


@upgrade_table.register(description="Add cross-signing key and signature caches")
async def upgrade_v5(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE crypto_cross_signing_keys (
            user_id TEXT,
            usage   TEXT,
            key     CHAR(43),
            first_seen_key CHAR(43),
            PRIMARY KEY (user_id, usage)
        )"""
    )
    await conn.execute(
        """CREATE TABLE crypto_cross_signing_signatures (
            signed_user_id TEXT,
            signed_key     TEXT,
            signer_user_id TEXT,
            signer_key     TEXT,
            signature      TEXT,
            PRIMARY KEY (signed_user_id, signed_key, signer_user_id, signer_key)
        )"""
    )


@upgrade_table.register(description="Update trust state values")
async def upgrade_v6(conn: Connection) -> None:
    await conn.execute("UPDATE crypto_device SET trust=300 WHERE trust=1")  # verified
    await conn.execute("UPDATE crypto_device SET trust=-100 WHERE trust=2")  # blacklisted
    await conn.execute("UPDATE crypto_device SET trust=0 WHERE trust=3")  # ignored -> unset


@upgrade_table.register(
    description="Synchronize schema with mautrix-go", upgrades_to=9, transaction=False
)
async def upgrade_v9(conn: Connection, scheme: Scheme) -> None:
    if scheme == Scheme.POSTGRES:
        async with conn.transaction():
            await upgrade_v9_postgres(conn)
    else:
        await upgrade_v9_sqlite(conn)


# These two are never used because the previous one jumps from 6 to 9.
@upgrade_table.register
async def upgrade_noop_7_to_8(_: Connection) -> None:
    pass


@upgrade_table.register
async def upgrade_noop_8_to_9(_: Connection) -> None:
    pass


async def upgrade_v9_postgres(conn: Connection) -> None:
    await conn.execute("UPDATE crypto_account SET device_id='' WHERE device_id IS NULL")
    await conn.execute("ALTER TABLE crypto_account ALTER COLUMN device_id SET NOT NULL")

    await conn.execute(
        "ALTER TABLE crypto_megolm_inbound_session ALTER COLUMN signing_key DROP NOT NULL"
    )
    await conn.execute(
        "ALTER TABLE crypto_megolm_inbound_session ALTER COLUMN session DROP NOT NULL"
    )
    await conn.execute(
        "ALTER TABLE crypto_megolm_inbound_session ALTER COLUMN forwarding_chains DROP NOT NULL"
    )
    await conn.execute("ALTER TABLE crypto_megolm_inbound_session ADD COLUMN withheld_code TEXT")
    await conn.execute("ALTER TABLE crypto_megolm_inbound_session ADD COLUMN withheld_reason TEXT")

    await conn.execute("DELETE FROM crypto_cross_signing_keys WHERE key IS NULL")
    await conn.execute(
        "UPDATE crypto_cross_signing_keys SET first_seen_key=key WHERE first_seen_key IS NULL"
    )
    await conn.execute("ALTER TABLE crypto_cross_signing_keys ALTER COLUMN key SET NOT NULL")
    await conn.execute(
        "ALTER TABLE crypto_cross_signing_keys ALTER COLUMN first_seen_key SET NOT NULL"
    )

    await conn.execute("DELETE FROM crypto_cross_signing_signatures WHERE signature IS NULL")
    await conn.execute(
        "ALTER TABLE crypto_cross_signing_signatures ALTER COLUMN signature SET NOT NULL"
    )

    await conn.execute(
        "ALTER TABLE crypto_megolm_outbound_session ALTER COLUMN max_age TYPE BIGINT "
        "USING (EXTRACT(EPOCH from max_age)*1000)::bigint"
    )


async def upgrade_v9_sqlite(conn: Connection) -> None:
    await conn.execute("PRAGMA foreign_keys = OFF")
    async with conn.transaction():
        await conn.execute(
            """CREATE TABLE new_crypto_account (
                account_id TEXT    PRIMARY KEY,
                device_id  TEXT    NOT NULL,
                shared     BOOLEAN NOT NULL,
                sync_token TEXT    NOT NULL,
                account    bytea   NOT NULL
            )"""
        )
        await conn.execute(
            """
            INSERT INTO new_crypto_account (account_id, device_id, shared, sync_token, account)
            SELECT account_id, COALESCE(device_id, ''), shared, sync_token, account
            FROM crypto_account
            """
        )
        await conn.execute("DROP TABLE crypto_account")
        await conn.execute("ALTER TABLE new_crypto_account RENAME TO crypto_account")

        await conn.execute(
            """CREATE TABLE new_crypto_megolm_inbound_session (
                account_id        TEXT,
                session_id        CHAR(43),
                sender_key        CHAR(43)  NOT NULL,
                signing_key       CHAR(43),
                room_id           TEXT      NOT NULL,
                session           bytea,
                forwarding_chains TEXT,
                withheld_code     TEXT,
                withheld_reason   TEXT,
                PRIMARY KEY (account_id, session_id)
            )"""
        )
        await conn.execute(
            """
            INSERT INTO new_crypto_megolm_inbound_session (
                account_id, session_id, sender_key, signing_key, room_id, session,
                forwarding_chains
            )
            SELECT account_id, session_id, sender_key, signing_key, room_id, session,
                   forwarding_chains
            FROM crypto_megolm_inbound_session
            """
        )
        await conn.execute("DROP TABLE crypto_megolm_inbound_session")
        await conn.execute(
            "ALTER TABLE new_crypto_megolm_inbound_session RENAME TO crypto_megolm_inbound_session"
        )

        await conn.execute("UPDATE crypto_megolm_outbound_session SET max_age=max_age*1000")

        await conn.execute(
            """CREATE TABLE new_crypto_cross_signing_keys (
                user_id TEXT,
                usage   TEXT,
                key     CHAR(43) NOT NULL,

                first_seen_key CHAR(43) NOT NULL,

                PRIMARY KEY (user_id, usage)
            )"""
        )
        await conn.execute(
            """
            INSERT INTO new_crypto_cross_signing_keys (user_id, usage, key, first_seen_key)
            SELECT user_id, usage, key, COALESCE(first_seen_key, key)
            FROM crypto_cross_signing_keys
            WHERE key IS NOT NULL
            """
        )
        await conn.execute("DROP TABLE crypto_cross_signing_keys")
        await conn.execute(
            "ALTER TABLE new_crypto_cross_signing_keys RENAME TO crypto_cross_signing_keys"
        )

        await conn.execute(
            """CREATE TABLE new_crypto_cross_signing_signatures (
                signed_user_id TEXT,
                signed_key     TEXT,
                signer_user_id TEXT,
                signer_key     TEXT,
                signature      CHAR(88) NOT NULL,
                PRIMARY KEY (signed_user_id, signed_key, signer_user_id, signer_key)
            )"""
        )
        await conn.execute(
            """
            INSERT INTO new_crypto_cross_signing_signatures (
                signed_user_id, signed_key, signer_user_id, signer_key, signature
            )
            SELECT signed_user_id, signed_key, signer_user_id, signer_key, signature
            FROM crypto_cross_signing_signatures
            WHERE signature IS NOT NULL
            """
        )
        await conn.execute("DROP TABLE crypto_cross_signing_signatures")
        await conn.execute(
            "ALTER TABLE new_crypto_cross_signing_signatures "
            "RENAME TO crypto_cross_signing_signatures"
        )

        await conn.execute("PRAGMA foreign_key_check")
    await conn.execute("PRAGMA foreign_keys = ON")


@upgrade_table.register(
    description="Add metadata for detecting when megolm sessions are safe to delete"
)
async def upgrade_v10(conn: Connection) -> None:
    await conn.execute("ALTER TABLE crypto_megolm_inbound_session ADD COLUMN ratchet_safety jsonb")
    await conn.execute(
        "ALTER TABLE crypto_megolm_inbound_session ADD COLUMN received_at timestamp"
    )
    await conn.execute("ALTER TABLE crypto_megolm_inbound_session ADD COLUMN max_age BIGINT")
    await conn.execute("ALTER TABLE crypto_megolm_inbound_session ADD COLUMN max_messages INTEGER")
    await conn.execute(
        "ALTER TABLE crypto_megolm_inbound_session "
        "ADD COLUMN is_scheduled BOOLEAN NOT NULL DEFAULT false"
    )
