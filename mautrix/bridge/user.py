# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from collections import defaultdict
from abc import ABC, abstractmethod
import logging
import asyncio

from mautrix.api import Method, UnstableClientPath
from mautrix.appservice import AppService
from mautrix.types import UserID, RoomID, EventType, Membership
from mautrix.errors import MNotFound
from mautrix.util.logging import TraceLogger
from mautrix.util.opt_prometheus import Gauge
from mautrix.util.bridge_state import BridgeState, BridgeStateEvent

from .portal import BasePortal
from .puppet import BasePuppet

if TYPE_CHECKING:
    from .bridge import Bridge

AsmuxPath = UnstableClientPath["com.beeper.asmux"]


class BaseUser(ABC):
    log: TraceLogger = logging.getLogger("mau.user")
    _async_get_locks: Dict[Any, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    az: AppService
    bridge: 'Bridge'
    loop: asyncio.AbstractEventLoop

    is_whitelisted: bool
    is_admin: bool
    mxid: UserID

    dm_update_lock: asyncio.Lock
    command_status: Optional[Dict[str, Any]]
    _metric_value: Dict[Gauge, bool]
    _prev_bridge_status: Optional[BridgeState]

    def __init__(self) -> None:
        self.dm_update_lock = asyncio.Lock()
        self.command_status = None
        self._metric_value = defaultdict(lambda: False)
        self._prev_bridge_status = None
        self.log = self.log.getChild(self.mxid)

    @abstractmethod
    async def is_logged_in(self) -> bool:
        raise NotImplementedError()

    async def get_puppet(self) -> Optional['BasePuppet']:
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
                try:
                    current_dms = await puppet.intent.get_account_data(EventType.DIRECT)
                except MNotFound:
                    current_dms = {}
                if replace:
                    # Filter away all existing DM statuses with bridge users
                    filtered_dms = {user: rooms for user, rooms in current_dms.items()
                                    if not self.bridge.is_bridge_ghost(user)}
                else:
                    filtered_dms = current_dms
                # Add DM statuses for all rooms in our database
                new_dms = {**filtered_dms, **dms}
                if current_dms != new_dms:
                    await puppet.intent.set_account_data(EventType.DIRECT, new_dms)

    def _track_metric(self, metric: Gauge, value: bool) -> None:
        if self._metric_value[metric] != value:
            if value:
                metric.inc(1)
            else:
                metric.dec(1)
            self._metric_value[metric] = value

    async def fill_bridge_state(self, state: BridgeState) -> None:
        state.user_id = self.mxid
        state.fill()

    async def push_bridge_state(self, state_event: BridgeStateEvent, error: Optional[str] = None,
                                message: Optional[str] = None, ttl: Optional[int] = None,
                                remote_id: Optional[str] = None) -> None:
        state = BridgeState(
            state_event=state_event,
            error=error,
            message=message,
            ttl=ttl,
            remote_id=remote_id,
        )
        await self.fill_bridge_state(state)
        if state.should_deduplicate(self._prev_bridge_status):
            return
        self._prev_bridge_status = state
        await state.send(self.bridge.config["homeserver.status_endpoint"],
                         self.az.as_token, self.log)
