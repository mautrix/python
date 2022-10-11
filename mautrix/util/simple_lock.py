# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import asyncio
import logging


class SimpleLock:
    _event: asyncio.Event
    log: logging.Logger | None
    message: str | None
    noop_mode: bool

    def __init__(
        self,
        message: str | None = None,
        log: logging.Logger | None = None,
        noop_mode: bool = False,
    ) -> None:
        self.noop_mode = noop_mode
        if not noop_mode:
            self._event = asyncio.Event()
            self._event.set()
        self.log = log
        self.message = message

    def __enter__(self) -> None:
        if not self.noop_mode:
            self._event.clear()

    async def __aenter__(self) -> None:
        self.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self.noop_mode:
            self._event.set()

    def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)

    @property
    def locked(self) -> bool:
        return not self.noop_mode and not self._event.is_set()

    async def wait(self, task: str | None = None) -> None:
        if not self.noop_mode and not self._event.is_set():
            if self.log and self.message:
                self.log.debug(self.message, task)
            await self._event.wait()
