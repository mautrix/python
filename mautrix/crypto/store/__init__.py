from mautrix import __optional_imports__

from .abstract import CryptoStore, StateStore
from .memory import MemoryCryptoStore

try:
    from .asyncpg import PgCryptoStateStore, PgCryptoStore
except ImportError:
    if __optional_imports__:
        raise
    PgCryptoStore = PgCryptoStateStore = None

__all__ = ["CryptoStore", "StateStore", "MemoryCryptoStore", "PgCryptoStateStore", "PgCryptoStore"]
