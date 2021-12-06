# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
import asyncio
import logging

import asyncpg

from .database import AcquireResult, Database
from .upgrade import UpgradeTable


class PostgresDatabase(Database):
    scheme = "postgres"
    _pool: asyncpg.pool.Pool | None
    _pool_override: bool

    def __init__(
        self,
        url: str,
        upgrade_table: UpgradeTable,
        db_args: dict[str, Any] = None,
        log: logging.Logger | None = None,
    ) -> None:
        super().__init__(url, db_args=db_args, upgrade_table=upgrade_table, log=log)
        self._pool = None
        self._pool_override = False

    def override_pool(self, db: PostgresDatabase) -> None:
        self._pool = db._pool
        self._pool_override = True

    async def start(self) -> None:
        if not self._pool_override:
            self._db_args["loop"] = asyncio.get_running_loop()
            self.log.debug(f"Connecting to {self.url}")
            self._pool = await asyncpg.create_pool(self.url, **self._db_args)
        await super().start()

    @property
    def pool(self) -> asyncpg.pool.Pool:
        if not self._pool:
            raise RuntimeError("Database has not been started")
        return self._pool

    async def stop(self) -> None:
        if not self._pool_override:
            await self.pool.close()

    def acquire(self) -> AcquireResult:
        return self.pool.acquire()


Database.schemes["postgres"] = PostgresDatabase
Database.schemes["postgresql"] = PostgresDatabase
