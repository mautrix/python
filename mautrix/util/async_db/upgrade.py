# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Awaitable, Callable
import functools
import inspect
import logging

from mautrix import __optional_imports__
from mautrix.util.logging import TraceLogger

from .. import async_db

if __optional_imports__:
    from asyncpg import Connection

Upgrade = Callable[["Connection", str], Awaitable[None]]


class UnsupportedDatabaseVersion(Exception):
    pass


async def noop_upgrade(_: Connection) -> None:
    pass


def table_exists(scheme: str, name: str) -> str:
    if scheme == "sqlite":
        return f"SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='{name}')"
    elif scheme == "postgres":
        return f"SELECT EXISTS(SELECT FROM information_schema.tables WHERE table_name='{name}')"
    raise RuntimeError("unsupported database scheme")


def column_exists(scheme: str, table: str, column: str) -> str:
    if scheme == "sqlite":
        return f"SELECT EXISTS(SELECT 1 FROM pragma_table_info('{table}') WHERE name='{column}')"
    elif scheme == "postgres":
        return (
            f"SELECT EXISTS(SELECT FROM information_schema.columns "
            f"WHERE table_name='{table}' AND column_name='{column}')"
        )
    raise RuntimeError("unsupported database scheme")


class UpgradeTable:
    upgrades: list[Upgrade]
    allow_unsupported: bool
    database_name: str
    version_table_name: str
    version_table_namespace: str
    log: TraceLogger

    def __init__(
        self,
        allow_unsupported: bool = False,
        version_table_name: str = "version",
        version_table_namespace: str = "main",
        database_name: str = "database",
        log: logging.Logger | TraceLogger | None = None,
    ) -> None:
        self.upgrades = [noop_upgrade]
        self.allow_unsupported = allow_unsupported
        self.version_table_name = version_table_name
        self.version_table_namespace = version_table_namespace
        self.database_name = database_name
        self.log = log or logging.getLogger("mau.db.upgrade")

    def register(
        self,
        index: int = -1,
        description: str = "",
        _outer_fn: Upgrade | None = None,
        transaction: bool = True,
    ) -> Upgrade | Callable[[Upgrade], Upgrade] | None:
        if isinstance(index, str):
            description = index
            index = -1

        def actually_register(fn: Upgrade) -> Upgrade:
            params = inspect.signature(fn).parameters
            if len(params) == 1:
                _wrapped: Callable[[Connection], Awaitable[None]] = fn

                @functools.wraps(_wrapped)
                async def _wrapper(conn: Connection, _: str) -> None:
                    return await _wrapped(conn)

                fn = _wrapper

            fn.__mau_db_upgrade_description__ = description
            fn.__mau_db_upgrade_transaction__ = transaction
            if index == -1 or index == len(self.upgrades):
                self.upgrades.append(fn)
            else:
                if len(self.upgrades) <= index:
                    self.upgrades += [noop_upgrade] * (index - len(self.upgrades) + 1)
                self.upgrades[index] = fn
            return fn

        return actually_register(_outer_fn) if _outer_fn else actually_register

    @staticmethod
    async def _create_version_table(conn: Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE version (
                namespace TEXT    PRIMARY KEY,
                version   INTEGER NOT NULL
            )
        """
        )

    async def _upgrade_version_table(self, scheme: str, conn: Connection) -> None:
        if not await conn.fetchval(table_exists(scheme, "version")):
            self.log.debug("Creating db schema version table (v2)")
            await self._create_version_table(conn)
        elif not await conn.fetchval(column_exists(scheme, "version", "namespace")):
            if self.version_table_name != "version":
                raise RuntimeError("Can't upgrade version table with a non-primary UpgradeTable")
            self.log.debug("Upgrading db schema version table from v1 to v2")
            current_main_version = await conn.fetchval("SELECT version FROM version LIMIT 1")
            await conn.execute("DROP TABLE version")
            await self._create_version_table(conn)
            self.log.debug(
                f"Inserting main schema version {current_main_version} into updated version table"
            )
            await conn.execute(
                self._version_insert_query, self.version_table_namespace, current_main_version
            )

        if self.version_table_name != "version" and await conn.fetchval(
            table_exists(scheme, self.version_table_name)
        ):
            current_own_version = await conn.fetchval(
                f"SELECT version FROM {self.version_table_name} LIMIT 1"
            )
            self.log.debug(
                f"Inserting {self.version_table_namespace} schema version "
                f"{current_own_version} into updated version table "
                f"and deleting legacy {self.version_table_name} table"
            )
            await conn.execute(
                self._version_insert_query, self.version_table_namespace, current_own_version
            )
            await conn.execute(f"DELETE TABLE {self.version_table_name}")

    _version_insert_query = (
        "INSERT INTO version (namespace, version) VALUES ($1, $2) "
        "ON CONFLICT (namespace) DO UPDATE SET version=$2"
    )

    async def _save_version(self, conn: Connection, version: int) -> None:
        self.log.trace(f"Saving current version (v{version}) to database")
        await conn.execute(self._version_insert_query, self.version_table_namespace, version)

    async def upgrade(self, db: async_db.Database) -> None:
        async with db.acquire() as conn, conn.transaction():
            await self._upgrade_version_table(db.scheme, conn)
        version: int = (
            await db.fetchval(
                f"SELECT version FROM version WHERE namespace=$1", self.version_table_namespace
            )
            or 0
        )

        if len(self.upgrades) < version:
            error = (
                f"Unsupported database version v{version} "
                f"(latest known is v{len(self.upgrades) - 1})"
            )
            if not self.allow_unsupported:
                raise UnsupportedDatabaseVersion(error)
            else:
                self.log.warning(error)
                return
        elif len(self.upgrades) == version:
            self.log.debug(f"Database at v{version}, not upgrading")
            return

        async with db.acquire() as conn:
            for new_version in range(version + 1, len(self.upgrades)):
                upgrade = self.upgrades[new_version]
                desc = getattr(upgrade, "__mau_db_upgrade_description__", None)
                suffix = f": {desc}" if desc else ""
                self.log.debug(
                    f"Upgrading {self.database_name} from v{version} to v{new_version}{suffix}"
                )
                if getattr(upgrade, "__mau_db_upgrade_transaction__", True):
                    async with conn.transaction():
                        await upgrade(conn, db.scheme)
                        version = new_version
                        await self._save_version(conn, version)
                else:
                    await upgrade(conn, db.scheme)
                    version = new_version
                    await self._save_version(conn, version)


upgrade_tables: dict[str, UpgradeTable] = {}


def register_upgrade_table_parent_module(name: str) -> None:
    upgrade_tables[name] = UpgradeTable()


def _find_upgrade_table(fn: Upgrade) -> UpgradeTable:
    try:
        module = fn.__module__
    except AttributeError as e:
        raise ValueError(
            "Registering upgrades without an UpgradeTable requires the function "
            "to have the __module__ attribute."
        ) from e
    parts = module.split(".")
    used_parts = []
    last_error = None
    for part in parts:
        used_parts.append(part)
        try:
            return upgrade_tables[".".join(used_parts)]
        except KeyError as e:
            last_error = e
    raise KeyError(
        "Registering upgrades without an UpgradeTable requires you to register a parent "
        "module with register_upgrade_table_parent_module first."
    ) from last_error


def register_upgrade(index: int = -1, description: str = "") -> Callable[[Upgrade], Upgrade]:
    def actually_register(fn: Upgrade) -> Upgrade:
        return _find_upgrade_table(fn).register(index, description, fn)

    return actually_register
