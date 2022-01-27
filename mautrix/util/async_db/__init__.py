from mautrix import __optional_imports__

from .database import Database
from .upgrade import UpgradeTable, column_exists, register_upgrade, table_exists

try:
    from .asyncpg import PostgresDatabase
except ImportError:
    if __optional_imports__:
        raise
    PostgresDatabase = None

try:
    from .aiosqlite import SQLiteDatabase
except ImportError:
    if __optional_imports__:
        raise
    SQLiteDatabase = None

__all__ = ["Database", "UpgradeTable", "register_upgrade", "PostgresDatabase", "SQLiteDatabase"]
