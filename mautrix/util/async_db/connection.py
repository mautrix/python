# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Callable, TypeVar
from contextlib import asynccontextmanager
from logging import WARNING
import functools
import time

from mautrix import __optional_imports__
from mautrix.util.logging import SILLY, TraceLogger

from .scheme import Scheme

if __optional_imports__:
    from sqlite3 import Row

    from asyncpg import Record
    import asyncpg

    from . import aiosqlite

Decorated = TypeVar("Decorated", bound=Callable[..., Any])
LOG_MESSAGE = "%s(%r) took %.3f seconds"


def log_duration(func: Decorated) -> Decorated:
    func_name = func.__name__

    @functools.wraps(func)
    async def wrapper(self: LoggingConnection, arg: str, *args: Any, **kwargs: str) -> Any:
        start = time.monotonic()
        ret = await func(self, arg, *args, **kwargs)
        duration = time.monotonic() - start
        self.log.log(WARNING if duration > 1 else SILLY, LOG_MESSAGE, func_name, arg, duration)
        return ret

    return wrapper


class LoggingConnection:
    scheme: Scheme
    wrapped: aiosqlite.TxnConnection | asyncpg.Connection
    log: TraceLogger

    def __init__(
        self,
        scheme: Scheme,
        wrapped: aiosqlite.TxnConnection | asyncpg.Connection,
        log: TraceLogger,
    ) -> None:
        self.scheme = scheme
        self.wrapped = wrapped
        self.log = log
        self._inited = True

    def __setattr__(self, key: str, value: Any) -> None:
        if getattr(self, "_inited", False):
            raise RuntimeError("LoggingConnection fields are frozen")
        super().__setattr__(key, value)

    @asynccontextmanager
    async def transaction(self) -> None:
        async with self.wrapped.transaction():
            yield

    @log_duration
    async def execute(self, query: str, *args: Any, timeout: float | None = None) -> str:
        return await self.wrapped.execute(query, *args, timeout=timeout)

    @log_duration
    async def executemany(self, query: str, *args: Any, timeout: float | None = None) -> str:
        return await self.wrapped.executemany(query, *args, timeout=timeout)

    @log_duration
    async def fetch(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> list[Row | Record]:
        return await self.wrapped.fetch(query, *args, timeout=timeout)

    @log_duration
    async def fetchval(
        self, query: str, *args: Any, column: int = 0, timeout: float | None = None
    ) -> Any:
        return await self.wrapped.fetchval(query, *args, column=column, timeout=timeout)

    @log_duration
    async def fetchrow(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> Row | Record | None:
        return await self.wrapped.fetchrow(query, *args, timeout=timeout)

    async def table_exists(self, name: str) -> bool:
        if self.scheme == Scheme.SQLITE:
            return await self.fetchval(
                "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name=?1)", name
            )
        elif self.scheme in (Scheme.POSTGRES, Scheme.COCKROACH):
            return await self.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)", name
            )
        else:
            raise RuntimeError(f"Unknown scheme {self.scheme}")

    @log_duration
    async def copy_records_to_table(
        self,
        table_name: str,
        *,
        records: list[tuple[Any, ...]],
        columns: tuple[str, ...] | list[str],
        schema_name: str | None = None,
        timeout: float | None = None,
    ) -> None:
        if self.scheme != Scheme.POSTGRES:
            raise RuntimeError("copy_records_to_table is only supported on Postgres")
        return await self.wrapped.copy_records_to_table(
            table_name, records=records, columns=columns, schema_name=schema_name, timeout=timeout
        )
