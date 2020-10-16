# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from abc import ABC, abstractmethod
import logging
import asyncio

from mautrix.api import Method, UnstableClientPath
from mautrix.appservice import AppService
from mautrix.types import UserID, RoomID, EventType, Membership
from mautrix.errors import MNotFound
from mautrix.util.logging import TraceLogger
from mautrix.util.opt_prometheus import Gauge

from .portal import BasePortal

if TYPE_CHECKING:
    from .bridge import Bridge

AsmuxPath = UnstableClientPath["net.maunium.asmux"]


class BaseUser(ABC):
    log: TraceLogger = logging.getLogger("mau.user")
    az: AppService
    bridge: 'Bridge'
    loop: asyncio.AbstractEventLoop

    is_whitelisted: bool
    is_admin: bool
    mxid: UserID
    command_status: Optional[Dict[str, Any]]
    _metric_value: Dict[Gauge, bool]

    dm_update_lock: asyncio.Lock

    @abstractmethod
    async def is_logged_in(self) -> bool:
        raise NotImplementedError()

    async def is_in_portal(self, portal: BasePortal) -> bool:
        try:
            member_event = await portal.main_intent.get_state_event(
                portal.mxid, EventType.ROOM_MEMBER, self.mxid)
        except MNotFound:
            return False
        return member_event and member_event.membership in (Membership.JOIN, Membership.INVITE)

    async def get_direct_chats(self) -> Dict[UserID, List[RoomID]]:
        raise NotImplementedError()

    async def update_direct_chats(self, dms: Optional[Dict[UserID, List[RoomID]]] = None) -> None:
        """
        Update the m.direct account data of the user.

        Args:
            dms: DMs to _add_ to the list. If not provided, the list is _replaced_ with the result
                of :meth:`get_direct_chats`.
        """
        if not self.bridge.config["bridge.sync_direct_chat_list"]:
            return

        puppet = await self.bridge.get_double_puppet(self.mxid)
        if not puppet or not puppet.is_real_user:
            return

        self.log.debug("Updating m.direct list on homeserver")
        replace = dms is None
        dms = dms or await self.get_direct_chats()
        if self.bridge.config.get("homeserver.asmux", False):
            # This uses a secret endpoint for atomically updating the DM list
            await puppet.intent.api.request(Method.PUT if replace else Method.PATCH, AsmuxPath.dms,
                                            content=dms, headers={"X-Asmux-Auth": self.az.as_token})
        else:
            async with self.dm_update_lock:
                current_dms = await puppet.intent.get_account_data(EventType.DIRECT)
                if replace:
                    # Filter away all existing DM statuses with bridge users
                    current_dms = {user: rooms for user, rooms in current_dms.items()
                                   if not self.bridge.is_bridge_ghost(user)}
                # Add DM statuses for all rooms in our database
                current_dms.update(dms)
                await puppet.intent.set_account_data(EventType.DIRECT, current_dms)

    def _track_metric(self, metric: Gauge, value: bool) -> None:
        if self._metric_value[metric] != value:
            if value:
                metric.inc(1)
            else:
                metric.dec(1)
            self._metric_value[metric] = value
