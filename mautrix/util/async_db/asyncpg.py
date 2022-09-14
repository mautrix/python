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
import sys
import traceback

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
    _exit_on_ice: bool

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
        self._exit_on_ice = True
        if db_args:
            self._exit_on_ice = db_args.pop("meow_exit_on_ice", True)
            db_args.pop("init_commands", None)
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
            if self._pool:
                raise RuntimeError("Database has already been started")
            self._db_args["loop"] = asyncio.get_running_loop()
            log_url = self.url
            if log_url.password:
                log_url = log_url.with_password("password-redacted")
            self.log.debug(f"Connecting to {log_url}")
            self._pool = await asyncpg.create_pool(str(self.url), **self._db_args)
        await super().start()

    @property
    def pool(self) -> asyncpg.pool.Pool:
        if not self._pool:
            raise RuntimeError("Database has not been started")
        return self._pool

    async def stop(self) -> None:
        if not self._pool_override and self._pool is not None:
            await self._pool.close()

    async def _handle_exception(self, err: Exception) -> None:
        if self._exit_on_ice and isinstance(err, asyncpg.InternalClientError):
            pre_stack = traceback.format_stack()[:-2]
            post_stack = traceback.format_exception(err)
            header = post_stack[0]
            post_stack = post_stack[1:]
            self.log.critical(
                "Got asyncpg internal client error, exiting...\n%s%s%s",
                header,
                "".join(pre_stack),
                "".join(post_stack),
            )
            sys.exit(26)

    @asynccontextmanager
    async def acquire(self) -> LoggingConnection:
        async with self.pool.acquire() as conn:
            yield LoggingConnection(
                self.scheme, conn, self.log, handle_exception=self._handle_exception
            )


Database.schemes["postgres"] = PostgresDatabase
Database.schemes["postgresql"] = PostgresDatabase
Database.schemes["cockroach"] = PostgresDatabase
Database.schemes["cockroachdb"] = PostgresDatabase
