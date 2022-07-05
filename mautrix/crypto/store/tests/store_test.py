# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import AsyncContextManager, AsyncIterator, Callable
from contextlib import asynccontextmanager
import os
import random
import string
import time

import asyncpg
import pytest

from mautrix.client.state_store import SyncStore
from mautrix.crypto import InboundGroupSession, OlmAccount, OutboundGroupSession
from mautrix.types import DeviceID, EventID, RoomID, SessionID, SyncToken
from mautrix.util.async_db import Database

from .. import CryptoStore, MemoryCryptoStore, PgCryptoStore


@asynccontextmanager
async def async_postgres_store() -> AsyncIterator[PgCryptoStore]:
    try:
        pg_url = os.environ["MEOW_TEST_PG_URL"]
    except KeyError:
        pytest.skip("Skipped Postgres tests (MEOW_TEST_PG_URL not specified)")
        return
    conn: asyncpg.Connection = await asyncpg.connect(pg_url)
    schema_name = "".join(random.choices(string.ascii_lowercase, k=8))
    schema_name = f"test_schema_{schema_name}_{int(time.time())}"
    await conn.execute(f"CREATE SCHEMA {schema_name}")
    db = Database.create(
        pg_url,
        upgrade_table=PgCryptoStore.upgrade_table,
        db_args={"min_size": 1, "max_size": 3, "server_settings": {"search_path": schema_name}},
    )
    store = PgCryptoStore("", "test", db)
    await db.start()
    yield store
    await db.stop()
    await conn.execute(f"DROP SCHEMA {schema_name} CASCADE")
    await conn.close()


@asynccontextmanager
async def async_sqlite_store() -> AsyncIterator[PgCryptoStore]:
    db = Database.create(
        "sqlite:///:memory:", upgrade_table=PgCryptoStore.upgrade_table, db_args={"min_size": 1}
    )
    store = PgCryptoStore("", "test", db)
    await db.start()
    yield store
    await db.stop()


@asynccontextmanager
async def memory_store() -> AsyncIterator[MemoryCryptoStore]:
    yield MemoryCryptoStore("", "test")


@pytest.fixture(params=[async_postgres_store, async_sqlite_store, memory_store])
async def crypto_store(request) -> AsyncIterator[CryptoStore]:
    param: Callable[[], AsyncContextManager[CryptoStore]] = request.param
    async with param() as state_store:
        yield state_store


async def test_basic(crypto_store: CryptoStore) -> None:
    acc = OlmAccount()
    keys = acc.identity_keys
    await crypto_store.put_account(acc)
    await crypto_store.put_device_id(DeviceID("TEST"))
    if isinstance(crypto_store, SyncStore):
        await crypto_store.put_next_batch(SyncToken("TEST"))

    assert await crypto_store.get_device_id() == "TEST"
    assert (await crypto_store.get_account()).identity_keys == keys
    if isinstance(crypto_store, SyncStore):
        assert await crypto_store.get_next_batch() == "TEST"


def _make_group_sess(
    acc: OlmAccount, room_id: RoomID
) -> tuple[InboundGroupSession, OutboundGroupSession]:
    outbound = OutboundGroupSession(room_id)
    inbound = InboundGroupSession(
        session_key=outbound.session_key,
        signing_key=acc.signing_key,
        sender_key=acc.identity_key,
        room_id=room_id,
    )
    return inbound, outbound


async def test_validate_message_index(crypto_store: CryptoStore) -> None:
    acc = OlmAccount()

    inbound, outbound = _make_group_sess(acc, RoomID("!foo:bar.com"))
    outbound.shared = True
    orig_plaintext = "hello world"
    ciphertext = outbound.encrypt(orig_plaintext)
    ts = int(time.time() * 1000)
    plaintext, index = inbound.decrypt(ciphertext)
    assert plaintext == orig_plaintext

    assert await crypto_store.validate_message_index(
        acc.identity_key, SessionID(inbound.id), EventID("$foo"), index, ts
    ), "Initial validation returns True"
    assert await crypto_store.validate_message_index(
        acc.identity_key, SessionID(inbound.id), EventID("$foo"), index, ts
    ), "Validating the same details again returns True"
    assert not await crypto_store.validate_message_index(
        acc.identity_key, SessionID(inbound.id), EventID("$bar"), index, ts
    ), "Different event ID causes validation to fail"
    assert not await crypto_store.validate_message_index(
        acc.identity_key, SessionID(inbound.id), EventID("$foo"), index, ts + 1
    ), "Different timestamp causes validation to fail"
    assert not await crypto_store.validate_message_index(
        acc.identity_key, SessionID(inbound.id), EventID("$foo"), index, ts + 1
    ), "Validating incorrect details twice fails"
    assert await crypto_store.validate_message_index(
        acc.identity_key, SessionID(inbound.id), EventID("$foo"), index, ts
    ), "Validating the same details after fails still returns True"


# TODO tests for device identity storage, group session storage
#      and cross-signing key/signature storage
