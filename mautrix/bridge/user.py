# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, NamedTuple
from abc import ABC, abstractmethod
from collections import defaultdict, deque
import asyncio
import logging
import time

from mautrix.api import Method, Path
from mautrix.appservice import AppService
from mautrix.errors import MNotFound
from mautrix.types import EventID, EventType, Membership, MessageType, RoomID, UserID
from mautrix.util.bridge_state import BridgeState, BridgeStateEvent
from mautrix.util.logging import TraceLogger
from mautrix.util.message_send_checkpoint import (
    MessageSendCheckpoint,
    MessageSendCheckpointReportedBy,
    MessageSendCheckpointStatus,
    MessageSendCheckpointStep,
)
from mautrix.util.opt_prometheus import Gauge

from .. import bridge as br

AsmuxPath = Path.unstable["com.beeper.asmux"]


class WrappedTask(NamedTuple):
    task: asyncio.Task | None


class BaseUser(ABC):
    log: TraceLogger = logging.getLogger("mau.user")
    _async_get_locks: dict[Any, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    az: AppService
    bridge: br.Bridge
    loop: asyncio.AbstractEventLoop

    is_whitelisted: bool
    is_admin: bool
    relay_whitelisted: bool
    mxid: UserID

    dm_update_lock: asyncio.Lock
    command_status: dict[str, Any] | None
    _metric_value: dict[Gauge, bool]
    _prev_bridge_status: BridgeState | None
    _bridge_state_queue: deque[BridgeState]
    _bridge_state_loop: asyncio.Task | None

    def __init__(self) -> None:
        self.dm_update_lock = asyncio.Lock()
        self.command_status = None
        self._metric_value = defaultdict(lambda: False)
        self._prev_bridge_status = None
        self.log = self.log.getChild(self.mxid)
        self.relay_whitelisted = False
        self._bridge_state_queue = deque()
        self._bridge_state_loop = None

    @abstractmethod
    async def is_logged_in(self) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def get_puppet(self) -> br.BasePuppet | None:
        """
        Get the ghost that represents this Matrix user on the remote network.

        Returns:
            The puppet entity, or ``None`` if the user is not logged in,
            or it's otherwise not possible to find the remote ghost.
        """
        raise NotImplementedError()

    @abstractmethod
    async def get_portal_with(
        self, puppet: br.BasePuppet, create: bool = True
    ) -> br.BasePortal | None:
        """
        Get a private chat portal between this user and the given ghost.

        Args:
            puppet: The ghost who the portal should be with.
            create: ``True`` if the portal entity should be created if it doesn't exist.

        Returns:
            The portal entity, or ``None`` if it can't be found,
            or doesn't exist and ``create`` is ``False``.
        """

    async def needs_relay(self, portal: br.BasePortal) -> bool:
        return not await self.is_logged_in()

    async def is_in_portal(self, portal: br.BasePortal) -> bool:
        try:
            member_event = await portal.main_intent.get_state_event(
                portal.mxid, EventType.ROOM_MEMBER, self.mxid
            )
        except MNotFound:
            return False
        return member_event and member_event.membership in (Membership.JOIN, Membership.INVITE)

    async def get_direct_chats(self) -> dict[UserID, list[RoomID]]:
        raise NotImplementedError()

    async def update_direct_chats(self, dms: dict[UserID, list[RoomID]] | None = None) -> None:
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
        if self.bridge.homeserver_software.is_asmux:
            # This uses a secret endpoint for atomically updating the DM list
            await puppet.intent.api.request(
                Method.PUT if replace else Method.PATCH,
                AsmuxPath.dms,
                content=dms,
                headers={"X-Asmux-Auth": self.az.as_token},
            )
        else:
            async with self.dm_update_lock:
                try:
                    current_dms = await puppet.intent.get_account_data(EventType.DIRECT)
                except MNotFound:
                    current_dms = {}
                if replace:
                    # Filter away all existing DM statuses with bridge users
                    filtered_dms = {
                        user: rooms
                        for user, rooms in current_dms.items()
                        if not self.bridge.is_bridge_ghost(user)
                    }
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

    async def get_bridge_states(self) -> list[BridgeState]:
        raise NotImplementedError()

    async def push_bridge_state(
        self,
        state_event: BridgeStateEvent,
        error: str | None = None,
        message: str | None = None,
        ttl: int | None = None,
        remote_id: str | None = None,
        info: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        if not self.bridge.config["homeserver.status_endpoint"]:
            return

        state = BridgeState(
            state_event=state_event,
            error=error,
            message=message,
            ttl=ttl,
            remote_id=remote_id,
            info=info,
            reason=reason,
        )
        await self.fill_bridge_state(state)
        if state.should_deduplicate(self._prev_bridge_status):
            return
        self._prev_bridge_status = state
        self._bridge_state_queue.append(state)
        if not self._bridge_state_loop or self._bridge_state_loop.done():
            self.log.trace(f"Starting bridge state loop")
            self._bridge_state_loop = asyncio.create_task(self._start_bridge_state_send_loop())
        else:
            self.log.debug(f"Queued bridge state to send later: {state.state_event}")

    async def _start_bridge_state_send_loop(self):
        url = self.bridge.config["homeserver.status_endpoint"]
        while self._bridge_state_queue:
            state = self._bridge_state_queue.popleft()
            success = await state.send(url, self.az.as_token, self.log)
            if not success:
                if state.send_attempts_ <= 10:
                    retry_seconds = state.send_attempts_**2
                    self.log.warning(
                        f"Attempt #{state.send_attempts_} of sending bridge state "
                        f"{state.state_event} failed, retrying in {retry_seconds} seconds"
                    )
                    await asyncio.sleep(retry_seconds)
                    self._bridge_state_queue.appendleft(state)
                else:
                    self.log.error(
                        f"Failed to send bridge state {state.state_event} "
                        f"after {state.send_attempts_} attempts, giving up"
                    )
        self._bridge_state_loop = None

    def send_remote_checkpoint(
        self,
        status: MessageSendCheckpointStatus,
        event_id: EventID,
        room_id: RoomID,
        event_type: EventType,
        message_type: MessageType | None = None,
        error: str | Exception | None = None,
        retry_num: int = 0,
    ) -> WrappedTask:
        """
        Send a remote checkpoint for the given ``event_id``. This function spaws an
        :class:`asyncio.Task`` to send the checkpoint.

        :returns: the checkpoint send task. This can be awaited if you want to block on the
        checkpoint send.
        """
        if not self.bridge.config["homeserver.message_send_checkpoint_endpoint"]:
            return WrappedTask(task=None)
        task = asyncio.create_task(
            MessageSendCheckpoint(
                event_id=event_id,
                room_id=room_id,
                step=MessageSendCheckpointStep.REMOTE,
                timestamp=int(time.time() * 1000),
                status=status,
                reported_by=MessageSendCheckpointReportedBy.BRIDGE,
                event_type=event_type,
                message_type=message_type,
                info=str(error) if error else None,
                retry_num=retry_num,
            ).send(
                self.bridge.config["homeserver.message_send_checkpoint_endpoint"],
                self.az.as_token,
                self.log,
            )
        )
        return WrappedTask(task=task)
