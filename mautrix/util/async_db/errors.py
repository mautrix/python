# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations


class DatabaseException(RuntimeError):
    pass

    @property
    def explanation(self) -> str | None:
        return None


class UnsupportedDatabaseVersion(DatabaseException):
    def __init__(self, name: str, version: int, latest: int) -> None:
        super().__init__(
            f"Unsupported {name} schema version v{version} (latest known is v{latest})"
        )

    @property
    def explanation(self) -> str:
        return "Downgrading is not supported"


class ForeignTablesFound(DatabaseException):
    def __init__(self, explanation: str) -> None:
        super().__init__(f"The database contains foreign tables ({explanation})")

    @property
    def explanation(self) -> str:
        return "You can use --ignore-foreign-tables to ignore this error"


class DatabaseNotOwned(DatabaseException):
    def __init__(self, owner: str) -> None:
        super().__init__(f"The database is owned by {owner}")

    @property
    def explanation(self) -> str:
        return "Sharing the same database with different programs is not supported"
