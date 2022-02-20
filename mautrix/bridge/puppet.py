# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
from abc import ABC, abstractmethod
from collections import defaultdict
import asyncio
import logging

from mautrix.appservice import AppService, IntentAPI
from mautrix.types import UserID
from mautrix.util.logging import TraceLogger

from .. import bridge as br
from .custom_puppet import CustomPuppetMixin


class BasePuppet(CustomPuppetMixin, ABC):
    log: TraceLogger = logging.getLogger("mau.puppet")
    _async_get_locks: dict[Any, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    az: AppService
    loop: asyncio.AbstractEventLoop
    mx: br.BaseMatrixHandler

    is_registered: bool
    mxid: str
    intent: IntentAPI

    @classmethod
    @abstractmethod
    async def get_by_mxid(cls, mxid: UserID) -> BasePuppet:
        pass

    @classmethod
    @abstractmethod
    async def get_by_custom_mxid(cls, mxid: UserID) -> BasePuppet:
        pass
