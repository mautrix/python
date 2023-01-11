# Copyright (c) 2023 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import AsyncGenerator, Union
import logging

import aiohttp

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


class FileTooLargeError(Exception):
    def __init__(self, max_size: int) -> None:
        super().__init__(f"File size larger than maximum ({max_size / 1024 / 1024} MiB)")


_default_dl_log = logging.getLogger("mau.util.download")


async def read_response_chunks(
    resp: aiohttp.ClientResponse, max_size: int, log: logging.Logger = _default_dl_log
) -> bytearray:
    """
    Read the body from an aiohttp response in chunks into a mutable bytearray.

    Args:
        resp: The aiohttp response object to read the body from.
        max_size: The maximum size to read. FileTooLargeError will be raised if the Content-Length
            is higher than this, or if the body exceeds this size during reading.
        log: A logger for logging download status.

    Returns:
        The body data as a byte array.

    Raises:
        FileTooLargeError: if the body is larger than the provided max_size.
    """
    content_length = int(resp.headers.get("Content-Length", "0"))
    if 0 < max_size < content_length:
        raise FileTooLargeError(max_size)
    size_str = "unknown length" if content_length == 0 else f"{content_length} bytes"
    log.info(f"Reading file download response with {size_str} (max: {max_size})")
    data = bytearray(content_length)
    mv = memoryview(data) if content_length > 0 else None
    read_size = 0
    max_size += 1
    while True:
        block = await resp.content.readany()
        if not block:
            break
        max_size -= len(block)
        if max_size <= 0:
            raise FileTooLargeError(max_size)
        if len(data) >= read_size + len(block):
            mv[read_size : read_size + len(block)] = block
        elif len(data) > read_size:
            log.warning("File being downloaded is bigger than expected")
            mv[read_size:] = block[: len(data) - read_size]
            mv.release()
            mv = None
            data.extend(block[len(data) - read_size :])
        else:
            if mv is not None:
                mv.release()
                mv = None
            data.extend(block)
        read_size += len(block)
    if mv is not None:
        mv.release()
    log.info(f"Successfully read {read_size} bytes of file download response")
    return data


__all__ = ["AsyncBody", "FileTooLargeError", "async_iter_bytes", "async_read_bytes"]
