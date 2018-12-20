# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
from abc import ABC, abstractmethod

from .api.types import SyncToken


class ClientStore(ABC):
    """ClientStore persists high-level client stuff."""

    @property
    @abstractmethod
    def next_batch(self) -> SyncToken:
        return SyncToken("")

    @next_batch.setter
    @abstractmethod
    def next_batch(self, value: SyncToken) -> None:
        pass


class MemoryClientStore(ClientStore):
    """MemoryClientStore is a :class:`ClientStore` implementation that stores the data in memory."""

    def __init__(self, next_batch: Optional[SyncToken] = None) -> None:
        self._next_batch: Optional[SyncToken] = next_batch

    @property
    def next_batch(self) -> Optional[SyncToken]:
        return self._next_batch

    @next_batch.setter
    def next_batch(self, value: SyncToken) -> None:
        self._next_batch = value
