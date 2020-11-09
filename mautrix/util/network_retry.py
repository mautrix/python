# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Callable, Any
import asyncio
import logging

from mautrix.errors import MatrixRequestError, MatrixConnectionError
from .logging import TraceLogger

log: TraceLogger = logging.getLogger("mau.network-retry")


def linear_sleep(time: int = 5) -> Callable[[int], int]:
    return lambda _: time


def multiplying_sleep(base: int = 2) -> Callable[[int], int]:
    return lambda attempt: base * attempt


async def call_with_net_retry(func: Callable, *args: Any, _action: str, _attempts: int = 5,
                              _sleep_func: Callable[[int], int] = linear_sleep(), **kwargs: Any
                              ) -> Any:
    attempt_num = 0
    while True:
        if attempt_num >= _attempts:
            # This is the last attempt, don't catch anything
            return await func(*args, **kwargs)
        try:
            return await func(*args, **kwargs)
        except MatrixRequestError as e:
            if e.http_status not in (502, 504):
                raise
            error = f"Got gateway error trying to {_action}"
        except MatrixConnectionError as e:
            error = f"Got connection error trying to {_action}: {e}"
        attempt_num += 1
        sleep_time = _sleep_func(attempt_num)
        log.warning(f"{error}, retrying in {sleep_time} seconds")
        await asyncio.sleep(sleep_time)
