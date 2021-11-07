# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, List, Awaitable, Type, Dict, Union, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from urllib.parse import urlparse
import logging
import sys

from .upgrade import UpgradeTable, upgrade_tables

if TYPE_CHECKING:
    from asyncpg import Connection, Record

    from typing import Protocol


    class AcquireResult(Protocol):
        async def __aenter__(self) -> Connection: ...

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

        def __await__(self) -> Awaitable[Connection]: ...


class Database(ABC):
    schemes: Dict[str, Type['Database']] = {}
    log: logging.Logger

    scheme: str
    url: str
    _db_args: Dict[str, Any]
    upgrade_table: 'UpgradeTable'

    def __init__(self, url: str, upgrade_table: UpgradeTable,
                 db_args: Optional[Dict[str, Any]] = None,
                 log: Optional[logging.Logger] = None) -> None:
        self.url = url
        self._db_args = {**db_args} if db_args else {}
        self.upgrade_table = upgrade_table
        self.log = log or logging.getLogger("mau.db")

    @classmethod
    def create(cls, url: str, *, db_args: Optional[Dict[str, Any]] = None,
               upgrade_table: Union[None, UpgradeTable, str] = None,
               log: Optional[logging.Logger] = None) -> 'Database':
        scheme = urlparse(url).scheme
        try:
            impl = cls.schemes[scheme]
        except KeyError as e:
            if scheme in ("postgres", "postgresql"):
                raise RuntimeError(f"Unknown database scheme {scheme}."
                                   " Perhaps you forgot to install asyncpg?") from e
            elif scheme in ("sqlite", "sqlite3"):
                raise RuntimeError(f"Unknown database scheme {scheme}."
                                   " Perhaps you forgot to install aiosqlite?") from e
            raise RuntimeError(f"Unknown database scheme {scheme}") from e
        if isinstance(upgrade_table, str):
            upgrade_table = upgrade_tables[upgrade_table]
        elif upgrade_table is None:
            upgrade_table = UpgradeTable()
        elif not isinstance(upgrade_table, UpgradeTable):
            raise ValueError(f"Can't use {type(upgrade_table)} as the upgrade table")
        return impl(url, db_args=db_args, upgrade_table=upgrade_table, log=log)

    def override_pool(self, db: 'Database') -> None:
        pass

    async def start(self) -> None:
        try:
            await self.upgrade_table.upgrade(self)
        except Exception:
            self.log.critical("Failed to upgrade database", exc_info=True)
            sys.exit(25)

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    def acquire(self) -> 'AcquireResult':
        pass

    async def execute(self, query: str, *args: Any, timeout: Optional[float] = None) -> str:
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def fetch(self, query: str, *args: Any, timeout: Optional[float] = None
                    ) -> List['Record']:
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchval(self, query: str, *args: Any, column: int = 0,
                       timeout: Optional[float] = None) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)

    async def fetchrow(self, query: str, *args: Any, timeout: Optional[float] = None) -> 'Record':
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)
