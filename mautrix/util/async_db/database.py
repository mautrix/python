# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, AsyncContextManager, Type
from abc import ABC, abstractmethod
import logging

from yarl import URL

from mautrix import __optional_imports__
from mautrix.util.logging import TraceLogger

from .connection import LoggingConnection
from .errors import DatabaseNotOwned, ForeignTablesFound
from .scheme import Scheme
from .upgrade import UpgradeTable, upgrade_tables

if __optional_imports__:
    from aiosqlite import Cursor
    from asyncpg import Record


class Database(ABC):
    schemes: dict[str, Type[Database]] = {}
    log: TraceLogger

    scheme: Scheme
    url: URL
    _db_args: dict[str, Any]
    upgrade_table: UpgradeTable | None
    owner_name: str | None
    ignore_foreign_tables: bool

    def __init__(
        self,
        url: URL,
        upgrade_table: UpgradeTable | None,
        db_args: dict[str, Any] | None = None,
        log: TraceLogger | None = None,
        owner_name: str | None = None,
        ignore_foreign_tables: bool = True,
    ) -> None:
        self.url = url
        self._db_args = {**db_args} if db_args else {}
        self.upgrade_table = upgrade_table
        self.owner_name = owner_name
        self.ignore_foreign_tables = ignore_foreign_tables
        self.log = log or logging.getLogger("mau.db")
        assert isinstance(self.log, TraceLogger)

    @classmethod
    def create(
        cls,
        url: str | URL,
        *,
        db_args: dict[str, Any] | None = None,
        upgrade_table: UpgradeTable | str | None = None,
        log: logging.Logger | TraceLogger | None = None,
        owner_name: str | None = None,
        ignore_foreign_tables: bool = True,
    ) -> Database:
        url = URL(url)
        try:
            impl = cls.schemes[url.scheme]
        except KeyError as e:
            if url.scheme in ("postgres", "postgresql"):
                raise RuntimeError(
                    f"Unknown database scheme {url.scheme}."
                    " Perhaps you forgot to install asyncpg?"
                ) from e
            elif url.scheme in ("sqlite", "sqlite3"):
                raise RuntimeError(
                    f"Unknown database scheme {url.scheme}."
                    " Perhaps you forgot to install aiosqlite?"
                ) from e
            raise RuntimeError(f"Unknown database scheme {url.scheme}") from e
        if isinstance(upgrade_table, str):
            upgrade_table = upgrade_tables[upgrade_table]
        elif upgrade_table is None:
            upgrade_table = UpgradeTable()
        elif not isinstance(upgrade_table, UpgradeTable):
            raise ValueError(f"Can't use {type(upgrade_table)} as the upgrade table")
        return impl(
            url,
            db_args=db_args,
            upgrade_table=upgrade_table,
            log=log,
            owner_name=owner_name,
            ignore_foreign_tables=ignore_foreign_tables,
        )

    def override_pool(self, db: Database) -> None:
        pass

    async def start(self) -> None:
        if not self.ignore_foreign_tables:
            await self._check_foreign_tables()
        if self.owner_name:
            await self._check_owner()
        if self.upgrade_table and len(self.upgrade_table.upgrades) > 0:
            await self.upgrade_table.upgrade(self)

    async def _check_foreign_tables(self) -> None:
        if await self.table_exists("state_groups_state"):
            raise ForeignTablesFound("found state_groups_state likely belonging to Synapse")
        elif await self.table_exists("roomserver_rooms"):
            raise ForeignTablesFound("found roomserver_rooms likely belonging to Dendrite")

    async def _check_owner(self) -> None:
        await self.execute(
            """CREATE TABLE IF NOT EXISTS database_owner (
                key   INTEGER PRIMARY KEY DEFAULT 0,
                owner TEXT NOT NULL
            )"""
        )
        owner = await self.fetchval("SELECT owner FROM database_owner WHERE key=0")
        if not owner:
            await self.execute("INSERT INTO database_owner (owner) VALUES ($1)", self.owner_name)
        elif owner != self.owner_name:
            raise DatabaseNotOwned(owner)

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    def acquire(self) -> AsyncContextManager[LoggingConnection]:
        pass

    async def execute(self, query: str, *args: Any, timeout: float | None = None) -> str | Cursor:
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def executemany(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> str | Cursor:
        async with self.acquire() as conn:
            return await conn.executemany(query, *args, timeout=timeout)

    async def fetch(self, query: str, *args: Any, timeout: float | None = None) -> list[Record]:
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchval(
        self, query: str, *args: Any, column: int = 0, timeout: float | None = None
    ) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)

    async def fetchrow(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> Record | None:
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def table_exists(self, name: str) -> bool:
        async with self.acquire() as conn:
            return await conn.table_exists(name)
