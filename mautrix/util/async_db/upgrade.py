# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Callable, Awaitable, List, Dict, Optional, Union
import logging

import asyncpg

Upgrade = Callable[[asyncpg.Connection], Awaitable[None]]


class UnsupportedDatabaseVersion(Exception):
    pass


async def noop_upgrade(_: asyncpg.Connection) -> None:
    pass


class UpgradeTable:
    upgrades: List[Upgrade]
    allow_unsupported: bool
    log: logging.Logger

    def __init__(self, allow_unsupported: bool = False, log: Optional[logging.Logger] = None
                 ) -> None:
        self.upgrades = [noop_upgrade]
        self.allow_unsupported = allow_unsupported
        self.log = log or logging.getLogger("mau.db.upgrade")

    def register(self, index: int = -1, description: str = "", _outer_fn: Optional[Upgrade] = None
                 ) -> Union[Upgrade, Callable[[Upgrade], Upgrade]]:
        if isinstance(index, str):
            description = index
            index = -1

        def actually_register(fn: Upgrade) -> Upgrade:
            fn.__mau_db_upgrade_description__ = description
            if index == -1:
                self.upgrades.append(fn)
            else:
                if len(self.upgrades) <= index:
                    self.upgrades += [noop_upgrade] * (index - len(self.upgrades) + 1)
                self.upgrades[index] = fn
            return fn

        return actually_register(_outer_fn) if _outer_fn else actually_register

    async def upgrade(self, pool: asyncpg.pool.Pool) -> None:
        async with pool.acquire() as conn:
            await conn.execute("""CREATE TABLE IF NOT EXISTS version (
                version INTEGER PRIMARY KEY
            )""")
            row: asyncpg.Record = await conn.fetchrow("SELECT version FROM version LIMIT 1")
            version = row["version"] if row else 0

            if len(self.upgrades) < version:
                error = (f"Unsupported database version v{version} "
                         f"(latest known is v{len(self.upgrades) - 1})")
                if not self.allow_unsupported:
                    raise UnsupportedDatabaseVersion(error)
                else:
                    self.log.warning(error)
                    return
            elif len(self.upgrades) == version:
                self.log.debug(f"Database at v{version}, not upgrading")
                return

            for new_version in range(version + 1, len(self.upgrades)):
                upgrade = self.upgrades[new_version]
                desc = getattr(upgrade, "__mau_db_upgrade_description__", None)
                suffix = f": {desc}" if desc else ""
                self.log.debug(f"Upgrading database from v{version} to v{new_version}{suffix}")
                await upgrade(conn)
                version = new_version

            async with conn.transaction():
                self.log.debug(f"Saving current version (v{version}) to database")
                await conn.execute("DELETE FROM version")
                await conn.execute("INSERT INTO version (version) VALUES ($1)", version)


upgrade_tables: Dict[str, UpgradeTable] = {}


def register_upgrade_table_parent_module(name: str) -> None:
    upgrade_tables[name] = UpgradeTable()


def _find_upgrade_table(fn: Upgrade) -> UpgradeTable:
    try:
        module = fn.__module__
    except AttributeError as e:
        raise ValueError("Registering upgrades without an UpgradeTable requires the function "
                         "to have the __module__ attribute.") from e
    parts = module.split(".")
    used_parts = []
    last_error = None
    for part in parts:
        used_parts.append(part)
        try:
            return upgrade_tables[".".join(used_parts)]
        except KeyError as e:
            last_error = e
    raise KeyError("Registering upgrades without an UpgradeTable requires you to register a parent "
                   "module with register_upgrade_table_parent_module first.") from last_error


def register_upgrade(index: int = -1, description: str = "") -> Callable[[Upgrade], Upgrade]:
    def actually_register(fn: Upgrade) -> Upgrade:
        return _find_upgrade_table(fn).register(index, description, fn)

    return actually_register
