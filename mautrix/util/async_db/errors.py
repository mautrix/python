# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


class DatabaseException(RuntimeError):
    pass


class UnsupportedDatabaseVersion(DatabaseException):
    def __init__(self, name: str, version: int, latest: int) -> None:
        super().__init__(
            f"Unsupported {name} schema version v{version} (latest known is v{latest})"
        )


class ForeignTablesFound(DatabaseException):
    def __init__(self, explanation: str) -> None:
        super().__init__(f"The database contains foreign tables ({explanation})")


class DatabaseNotOwned(DatabaseException):
    def __init__(self, owner: str) -> None:
        super().__init__(f"The database is owned by {owner}")
