from mautrix import __optional_imports__

from .connection import LoggingConnection as Connection
from .database import Database
from .errors import (
    DatabaseException,
    DatabaseNotOwned,
    ForeignTablesFound,
    UnsupportedDatabaseVersion,
)
from .scheme import Scheme
from .upgrade import UpgradeTable, register_upgrade

try:
    from .asyncpg import PostgresDatabase
except ImportError:
    if __optional_imports__:
        raise
    PostgresDatabase = None

try:
    from aiosqlite import Cursor as SQLiteCursor

    from .aiosqlite import SQLiteDatabase
except ImportError:
    if __optional_imports__:
        raise
    SQLiteDatabase = None
    SQLiteCursor = None

__all__ = [
    "Database",
    "UpgradeTable",
    "register_upgrade",
    "PostgresDatabase",
    "SQLiteDatabase",
    "SQLiteCursor",
    "Connection",
    "Scheme",
    "DatabaseException",
    "DatabaseNotOwned",
    "UnsupportedDatabaseVersion",
    "ForeignTablesFound",
]
