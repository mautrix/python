# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any, Optional
from abc import ABC
import logging
import asyncio

from mautrix.appservice import AppService
from mautrix.types import UserID, EventType, Membership
from mautrix.errors import MNotFound
from mautrix.util.logging import TraceLogger

from .portal import BasePortal


class BaseUser(ABC):
    log: TraceLogger = logging.getLogger("mau.user")
    az: AppService
    loop: asyncio.AbstractEventLoop

    is_whitelisted: bool
    mxid: UserID
    command_status: Optional[Dict[str, Any]]

    async def is_logged_in(self) -> bool:
        return False

    async def is_in_portal(self, portal: BasePortal) -> bool:
        try:
            member_event = await portal.main_intent.get_state_event(
                portal.mxid, EventType.ROOM_MEMBER, self.mxid)
        except MNotFound:
            return False
        return member_event and member_event.membership in (Membership.JOIN, Membership.INVITE)
