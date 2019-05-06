# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import TYPE_CHECKING
from abc import ABC, abstractmethod
import asyncio
import logging

from mautrix.types import UserID
from mautrix.appservice import AppService, IntentAPI

from .custom_puppet import CustomPuppetMixin

if TYPE_CHECKING:
    from .matrix import BaseMatrixHandler


class BasePuppet(CustomPuppetMixin, ABC):
    log: logging.Logger = logging.getLogger("mau.puppet")
    az: AppService
    loop: asyncio.AbstractEventLoop
    mx: 'BaseMatrixHandler'

    is_registered: bool

    intent: IntentAPI

    mxid: str

    @abstractmethod
    def save(self) -> None:
        pass

    @classmethod
    @abstractmethod
    def get_by_mxid(cls, mxid: UserID) -> 'BasePuppet':
        pass
