# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import AsyncContextManager, AsyncIterator, Callable
from contextlib import asynccontextmanager
import json
import os
import pathlib
import random
import string
import time

import asyncpg
import pytest
import sqlalchemy as sql

from mautrix.types import EncryptionAlgorithm, Member, Membership, RoomID, StateEvent, UserID
from mautrix.util.async_db import Database
from mautrix.util.db import Base

from .. import MemoryStateStore, StateStore
from ..asyncpg import PgStateStore
from ..sqlalchemy import RoomState, SQLStateStore, UserProfile


@asynccontextmanager
async def async_postgres_store() -> AsyncIterator[PgStateStore]:
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
        upgrade_table=PgStateStore.upgrade_table,
        db_args={"min_size": 1, "max_size": 3, "server_settings": {"search_path": schema_name}},
    )
    store = PgStateStore(db)
    await db.start()
    yield store
    await db.stop()
    await conn.execute(f"DROP SCHEMA {schema_name} CASCADE")
    await conn.close()


@asynccontextmanager
async def async_sqlite_store() -> AsyncIterator[PgStateStore]:
    db = Database.create(
        "sqlite:///:memory:", upgrade_table=PgStateStore.upgrade_table, db_args={"min_size": 1}
    )
    store = PgStateStore(db)
    await db.start()
    yield store
    await db.stop()


@asynccontextmanager
async def alchemy_store() -> AsyncIterator[SQLStateStore]:
    db = sql.create_engine("sqlite:///:memory:")
    Base.metadata.bind = db
    for table in (RoomState, UserProfile):
        table.bind(db)
    Base.metadata.create_all()
    yield SQLStateStore()
    db.dispose()


@asynccontextmanager
async def memory_store() -> AsyncIterator[MemoryStateStore]:
    yield MemoryStateStore()


@pytest.fixture(params=[async_postgres_store, async_sqlite_store, alchemy_store, memory_store])
async def store(request) -> AsyncIterator[StateStore]:
    param: Callable[[], AsyncContextManager[StateStore]] = request.param
    async with param() as state_store:
        yield state_store


def read_state_file(request, file) -> dict[RoomID, list[StateEvent]]:
    path = pathlib.Path(request.node.fspath).with_name(file)
    with path.open() as fp:
        content = json.load(fp)
    return {
        room_id: [StateEvent.deserialize({**evt, "room_id": room_id}) for evt in events]
        for room_id, events in content.items()
    }


async def store_room_state(request, store: StateStore) -> None:
    room_state_changes = read_state_file(request, "new_state.json")
    for events in room_state_changes.values():
        for evt in events:
            await store.update_state(evt)


async def get_all_members(request, store: StateStore) -> None:
    room_state = read_state_file(request, "members.json")
    for room_id, member_events in room_state.items():
        await store.set_members(room_id, {evt.state_key: evt.content for evt in member_events})


async def get_joined_members(request, store: StateStore) -> None:
    path = pathlib.Path(request.node.fspath).with_name("joined_members.json")
    with path.open() as fp:
        content = json.load(fp)
    for room_id, members in content.items():
        parsed_members = {
            user_id: Member(
                membership=Membership.JOIN,
                displayname=member.get("display_name", ""),
                avatar_url=member.get("avatar_url", ""),
            )
            for user_id, member in members.items()
        }
        await store.set_members(room_id, parsed_members, only_membership=Membership.JOIN)


async def test_basic(store: StateStore) -> None:
    room_id = RoomID("!foo:example.com")
    user_id = UserID("@tulir:example.com")

    assert not await store.is_encrypted(room_id)
    assert not await store.is_joined(room_id, user_id)
    await store.joined(room_id, user_id)
    assert await store.is_joined(room_id, user_id)

    assert not await store.has_encryption_info_cached(RoomID("!unknown-room:example.com"))
    assert await store.is_encrypted(RoomID("!unknown-room:example.com")) is None


async def test_basic_updated(request, store: StateStore) -> None:
    await store_room_state(request, store)
    test_group = RoomID("!telegram-group:example.com")
    assert await store.is_encrypted(test_group)
    assert (await store.get_encryption_info(test_group)).algorithm == EncryptionAlgorithm.MEGOLM_V1
    assert not await store.is_encrypted(RoomID("!unencrypted-room:example.com"))


async def test_updates(request, store: StateStore) -> None:
    await store_room_state(request, store)
    room_id = RoomID("!telegram-group:example.com")
    initial_members = {"@tulir:example.com", "@telegram_84359547:example.com"}
    joined_members = initial_members | {
        "@telegrambot:example.com",
        "@telegram_5647382910:example.com",
        "@telegram_374880943:example.com",
        "@telegram_987654321:example.com",
        "@telegram_123456789:example.com",
    }
    left_members = {"@telegram_476034259:example.com", "@whatsappbot:example.com"}
    full_members = joined_members | left_members
    any_membership = (
        Membership.JOIN,
        Membership.INVITE,
        Membership.LEAVE,
        Membership.BAN,
        Membership.KNOCK,
    )
    leave_memberships = (Membership.BAN, Membership.LEAVE)
    assert set(await store.get_members(room_id)) == initial_members
    await get_all_members(request, store)
    assert set(await store.get_members(room_id)) == joined_members
    assert set(await store.get_members(room_id, memberships=any_membership)) == full_members
    await get_joined_members(request, store)
    assert set(await store.get_members(room_id)) == joined_members
    assert set(await store.get_members(room_id, memberships=any_membership)) == full_members
    assert set(await store.get_members(room_id, memberships=leave_memberships)) == left_members
    assert set(
        await store.get_members_filtered(
            room_id,
            memberships=leave_memberships,
            not_id="",
            not_prefix="@telegram_",
            not_suffix=":example.com",
        )
    ) == {"@whatsappbot:example.com"}
