# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, AsyncContextManager
from contextlib import asynccontextmanager
import asyncio
import logging
import os
import re
import sqlite3

from yarl import URL
import aiosqlite

from .connection import LoggingConnection
from .database import Database
from .scheme import Scheme
from .upgrade import UpgradeTable

POSITIONAL_PARAM_PATTERN = re.compile(r"\$(\d+)")


class TxnConnection(aiosqlite.Connection):
    def __init__(self, path: str, **kwargs) -> None:
        def connector() -> sqlite3.Connection:
            return sqlite3.connect(
                path, detect_types=sqlite3.PARSE_DECLTYPES, isolation_level=None, **kwargs
            )

        super().__init__(connector, iter_chunk_size=64)

    @asynccontextmanager
    async def transaction(self) -> None:
        await self.execute("BEGIN TRANSACTION")
        try:
            yield
        except Exception:
            await self.rollback()
            raise
        else:
            await self.commit()

    def __execute(self, query: str, *args: Any):
        query = POSITIONAL_PARAM_PATTERN.sub(r"?\1", query)
        return super().execute(query, args)

    async def execute(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> aiosqlite.Cursor:
        return await self.__execute(query, *args)

    async def executemany(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> aiosqlite.Cursor:
        query = POSITIONAL_PARAM_PATTERN.sub(r"?\1", query)
        return await super().executemany(query, *args)

    async def fetch(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> list[sqlite3.Row]:
        async with self.__execute(query, *args) as cursor:
            return list(await cursor.fetchall())

    async def fetchrow(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> sqlite3.Row | None:
        async with self.__execute(query, *args) as cursor:
            return await cursor.fetchone()

    async def fetchval(
        self, query: str, *args: Any, column: int = 0, timeout: float | None = None
    ) -> Any:
        row = await self.fetchrow(query, *args)
        if row is None:
            return None
        return row[column]


class SQLiteDatabase(Database):
    scheme = Scheme.SQLITE
    _parent: SQLiteDatabase | None
    _pool: asyncio.Queue[TxnConnection]
    _stopped: bool
    _conns: int
    _init_commands: list[str]

    def __init__(
        self,
        url: URL,
        upgrade_table: UpgradeTable,
        db_args: dict[str, Any] | None = None,
        log: logging.Logger | None = None,
        owner_name: str | None = None,
        ignore_foreign_tables: bool = True,
    ) -> None:
        super().__init__(
            url,
            db_args=db_args,
            upgrade_table=upgrade_table,
            log=log,
            owner_name=owner_name,
            ignore_foreign_tables=ignore_foreign_tables,
        )
        self._parent = None
        self._path = url.path
        self._pool = asyncio.Queue(self._db_args.pop("min_size", 1))
        self._db_args.pop("max_size", None)
        self._stopped = False
        self._conns = 0
        self._init_commands = self._add_missing_pragmas(self._db_args.pop("init_commands", []))

    @staticmethod
    def _add_missing_pragmas(init_commands: list[str]) -> list[str]:
        has_foreign_keys = False
        has_journal_mode = False
        has_synchronous = False
        has_busy_timeout = False
        for cmd in init_commands:
            if "PRAGMA" not in cmd:
                continue
            if "foreign_keys" in cmd:
                has_foreign_keys = True
            elif "journal_mode" in cmd:
                has_journal_mode = True
            elif "synchronous" in cmd:
                has_synchronous = True
            elif "busy_timeout" in cmd:
                has_busy_timeout = True
        if not has_foreign_keys:
            init_commands.append("PRAGMA foreign_keys = ON")
        if not has_journal_mode:
            init_commands.append("PRAGMA journal_mode = WAL")
        if not has_synchronous and "PRAGMA journal_mode = WAL" in init_commands:
            init_commands.append("PRAGMA synchronous = NORMAL")
        if not has_busy_timeout:
            init_commands.append("PRAGMA busy_timeout = 5000")
        return init_commands

    def override_pool(self, db: Database) -> None:
        assert isinstance(db, SQLiteDatabase)
        self._parent = db

    async def start(self) -> None:
        if self._parent:
            await super().start()
            return
        if self._conns:
            raise RuntimeError("database pool has already been started")
        elif self._stopped:
            raise RuntimeError("database pool can't be restarted")
        self.log.debug(f"Connecting to {self.url}")
        self.log.debug(f"Database connection init commands: {self._init_commands}")
        if os.path.exists(self._path):
            if not os.access(self._path, os.W_OK):
                self.log.warning("Database file doesn't seem writable")
        elif not os.access(os.path.dirname(os.path.abspath(self._path)), os.W_OK):
            self.log.warning("Database file doesn't exist and directory doesn't seem writable")
        for _ in range(self._pool.maxsize):
            conn = await TxnConnection(self._path, **self._db_args)
            if self._init_commands:
                cur = await conn.cursor()
                for command in self._init_commands:
                    self.log.trace("Executing init command: %s", command)
                    await cur.execute(command)
                await conn.commit()
            conn.row_factory = sqlite3.Row
            self._pool.put_nowait(conn)
            self._conns += 1
        await super().start()

    async def stop(self) -> None:
        if self._parent:
            return
        self._stopped = True
        while self._conns > 0:
            conn = await self._pool.get()
            self._conns -= 1
            await conn.close()

    def acquire(self) -> AsyncContextManager[LoggingConnection]:
        if self._parent:
            return self._parent.acquire()
        return self._acquire()

    @asynccontextmanager
    async def _acquire(self) -> LoggingConnection:
        if self._stopped:
            raise RuntimeError("database pool has been stopped")
        conn = await self._pool.get()
        try:
            yield LoggingConnection(self.scheme, conn, self.log)
        finally:
            self._pool.put_nowait(conn)


Database.schemes["sqlite"] = SQLiteDatabase
Database.schemes["sqlite3"] = SQLiteDatabase
