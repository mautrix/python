# Copyright (c) 2023 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import AsyncGenerator, Union

AsyncBody = AsyncGenerator[Union[bytes, bytearray, memoryview], None]


async def async_iter_bytes(data: bytearray | bytes, chunk_size: int = 1024**2) -> AsyncBody:
    """
    Return memory views into a byte array in chunks. This is used to prevent aiohttp from copying
    the entire request body.

    Args:
        data: The underlying data to iterate through.
        chunk_size: How big each returned chunk should be.

    Returns:
        An async generator that yields the given data in chunks.
    """
    with memoryview(data) as mv:
        for i in range(0, len(data), chunk_size):
            yield mv[i : i + chunk_size]


__all__ = ["AsyncBody", "async_iter_bytes"]
