# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import TYPE_CHECKING, Any
import functools

if TYPE_CHECKING:
    from typing import Awaitable, Callable, ParamSpec

    Param = ParamSpec("Param")
    Func = Callable[Param, Awaitable[Any]]


def async_getter_lock(fn: "Func") -> "Func":
    @functools.wraps(fn)
    async def wrapper(cls, *args, **kwargs) -> Any:
        async with cls._async_get_locks[args]:
            return await fn(cls, *args, **kwargs)

    return wrapper
