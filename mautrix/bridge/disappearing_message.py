# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import TypeVar
from abc import ABC, abstractmethod
import time

from attr import dataclass

from mautrix.types import EventID, RoomID


@dataclass
class AbstractDisappearingMessage(ABC):
    room_id: RoomID
    event_id: EventID
    expiration_seconds: int
    expiration_ts: int | None = None

    @abstractmethod
    async def insert(self) -> None:
        pass

    @abstractmethod
    async def update(self) -> None:
        pass

    def start_timer(self) -> None:
        self.expiration_ts = int(time.time() * 1000) + (self.expiration_seconds * 1000)

    @abstractmethod
    async def delete(self) -> None:
        pass

    @classmethod
    @abstractmethod
    async def get_all_scheduled(cls: type[DisappearingMessage]) -> list[DisappearingMessage]:
        pass

    @classmethod
    @abstractmethod
    async def get_unscheduled_for_room(
        cls: type[DisappearingMessage], room_id: RoomID
    ) -> list[DisappearingMessage]:
        pass


DisappearingMessage = TypeVar("DisappearingMessage", bound=AbstractDisappearingMessage)
