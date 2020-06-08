# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
import logging
import asyncio


class SimpleLock:
    _loop: asyncio.AbstractEventLoop
    _future: Optional[asyncio.Future]
    log: Optional[logging.Logger]
    message: Optional[str]

    def __init__(self, message: Optional[str] = None, log: Optional[logging.Logger] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._future = None
        self._loop = loop or asyncio.get_event_loop()
        self.log = log
        self.message = message

    def __enter__(self) -> None:
        if self._future is None or self._future.done():
            self._future = self._loop.create_future()

    async def __aenter__(self) -> None:
        self.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._future is not None:
            self._future.set_result(None)
            self._future = None

    def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)

    @property
    def locked(self) -> bool:
        return self._future is not None and not self._future.done()

    async def wait(self, task: Optional[str] = None) -> None:
        if self._future is not None:
            if self.log and self.message:
                self.log.debug(self.message, task)
            await self._future
