# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
import functools

from mautrix import __optional_imports__

if __optional_imports__:
    from typing import Awaitable, Callable, ParamSpec

    Param = ParamSpec("Param")
    Func = Callable[Param, Awaitable[Any]]


def async_getter_lock(fn: Func) -> Func:
    """
    A utility decorator for locking async getters that have caches
    (preventing race conditions between cache check and e.g. async database actions).

    The class must have an ```_async_get_locks`` defaultdict that contains :class:`asyncio.Lock`s
    (see example for exact definition). Non-cache-affecting arguments should be only passed as
    keyword args.

    Args:
        fn: The function to decorate.

    Returns:
        The decorated function.

    Examples:
        >>> import asyncio
        >>> from collections import defaultdict
        >>> class User:
        ...   _async_get_locks: dict[Any, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
        ...   db: Any
        ...   cache: dict[str, User]
        ...   @classmethod
        ...   @async_getter_lock
        ...   async def get(cls, id: str, *, create: bool = False) -> User | None:
        ...     try:
        ...       return cls.cache[id]
        ...     except KeyError:
        ...       pass
        ...     user = await cls.db.fetch_user(id)
        ...     if user:
        ...       return user
        ...     elif create:
        ...       return await cls.db.create_user(id)
        ...     return None
    """

    @functools.wraps(fn)
    async def wrapper(cls, *args, **kwargs) -> Any:
        async with cls._async_get_locks[args]:
            return await fn(cls, *args, **kwargs)

    return wrapper
