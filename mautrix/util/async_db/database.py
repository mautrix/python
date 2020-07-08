# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, Union, Any, List, Awaitable, TYPE_CHECKING
import asyncio
import logging
import sys

import asyncpg

from .upgrade import UpgradeTable, upgrade_tables

if TYPE_CHECKING:
    from typing import Protocol


    class AcquireResult(Protocol):
        async def __aenter__(self) -> asyncpg.Connection: ...

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

        def __await__(self) -> Awaitable[asyncpg.Connection]: ...


class Database:
    loop: asyncio.AbstractEventLoop
    log: logging.Logger

    _pool: Optional[asyncpg.pool.Pool]
    db_args: Dict[str, Any]
    upgrade_table: UpgradeTable

    url: str

    def __init__(self, url: str, db_args: Optional[Dict[str, Any]] = None,
                 upgrade_table: Union[None, UpgradeTable, str] = None,
                 log: Optional[logging.Logger] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.url = url
        self.db_args = db_args or {}
        if isinstance(upgrade_table, str):
            self.upgrade_table = upgrade_tables[upgrade_table]
        elif isinstance(upgrade_table, UpgradeTable):
            self.upgrade_table = upgrade_table
        elif upgrade_table is None:
            self.upgrade_table = UpgradeTable()
        else:
            raise ValueError(f"Can't use {type(upgrade_table)} as the upgrade table")
        self._pool = None
        self.log = log or logging.getLogger("mau.db")
        self.loop = loop or asyncio.get_event_loop()

    async def start(self) -> None:
        self.db_args["loop"] = self.loop
        self.log.debug(f"Connecting to {self.url}")
        self._pool = await asyncpg.create_pool(self.url, **self.db_args)
        try:
            await self.upgrade_table.upgrade(self.pool)
        except Exception:
            self.log.critical("Failed to upgrade database", exc_info=True)
            sys.exit(25)

    @property
    def pool(self) -> asyncpg.pool.Pool:
        if not self._pool:
            raise RuntimeError("Database has not been started")
        return self._pool

    async def stop(self) -> None:
        await self.pool.close()

    async def execute(self, query: str, *args: Any, timeout: Optional[float] = None) -> str:
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def fetch(self, query: str, *args: Any, timeout: Optional[float] = None
                    ) -> List[asyncpg.Record]:
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchval(self, query: str, *args: Any, column: int = 0,
                       timeout: Optional[float] = None) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)

    async def fetchrow(self, query: str, *args: Any, timeout: Optional[float] = None
                       ) -> asyncpg.Record:
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    def acquire(self) -> 'AcquireResult':
        return self.pool.acquire()
