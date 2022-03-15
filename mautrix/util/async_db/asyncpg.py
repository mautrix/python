# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
from contextlib import asynccontextmanager
import asyncio
import logging

from yarl import URL
import asyncpg

from .connection import LoggingConnection
from .database import Database
from .scheme import Scheme
from .upgrade import UpgradeTable


class PostgresDatabase(Database):
    scheme = Scheme.POSTGRES
    _pool: asyncpg.pool.Pool | None
    _pool_override: bool

    def __init__(
        self,
        url: URL,
        upgrade_table: UpgradeTable,
        db_args: dict[str, Any] = None,
        log: logging.Logger | None = None,
        owner_name: str | None = None,
        ignore_foreign_tables: bool = True,
    ) -> None:
        if url.scheme in ("cockroach", "cockroachdb"):
            self.scheme = Scheme.COCKROACH
            # Send postgres scheme to asyncpg
            url = url.with_scheme("postgres")
        super().__init__(
            url,
            db_args=db_args,
            upgrade_table=upgrade_table,
            log=log,
            owner_name=owner_name,
            ignore_foreign_tables=ignore_foreign_tables,
        )
        self._pool = None
        self._pool_override = False

    def override_pool(self, db: PostgresDatabase) -> None:
        self._pool = db._pool
        self._pool_override = True

    async def start(self) -> None:
        if not self._pool_override:
            self._db_args["loop"] = asyncio.get_running_loop()
            self.log.debug(f"Connecting to {self.url}")
            self._pool = await asyncpg.create_pool(str(self.url), **self._db_args)
        await super().start()

    @property
    def pool(self) -> asyncpg.pool.Pool:
        if not self._pool:
            raise RuntimeError("Database has not been started")
        return self._pool

    async def stop(self) -> None:
        if not self._pool_override:
            await self.pool.close()

    @asynccontextmanager
    async def acquire(self) -> LoggingConnection:
        async with self.pool.acquire() as conn:
            yield LoggingConnection(self.scheme, conn, self.log)


Database.schemes["postgres"] = PostgresDatabase
Database.schemes["postgresql"] = PostgresDatabase
Database.schemes["cockroach"] = PostgresDatabase
Database.schemes["cockroachdb"] = PostgresDatabase
