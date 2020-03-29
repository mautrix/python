# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
import asyncio
import logging

from mautrix.appservice import AppService, IntentAPI
from mautrix.types import RoomID, EventID, MessageEventContent

if TYPE_CHECKING:
    from .user import BaseUser


class BasePortal(ABC):
    log: logging.Logger = logging.getLogger("mau.portal")
    az: AppService
    loop: asyncio.AbstractEventLoop
    main_intent: IntentAPI
    mxid: Optional[RoomID]

    @abstractmethod
    async def handle_matrix_message(self, sender: 'BaseUser', message: MessageEventContent,
                                    event_id: EventID) -> None:
        pass
