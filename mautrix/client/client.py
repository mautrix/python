# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Callable, Union, Optional, Awaitable, Any, Type, TYPE_CHECKING
from enum import Enum, Flag, auto
from time import time
import asyncio
import inspect

from ..errors import MUnknownToken
from ..api import JSON
from .api.types import (EventType, MessageEvent, StateEvent, StrippedStateEvent, Event, FilterID,
                        Filter)
from .api import ClientAPI
from .store import ClientStore, MemoryClientStore

if TYPE_CHECKING:
    from .dispatcher import Dispatcher

EventHandler = Callable[[Event], Awaitable[None]]


class SyncStream(Flag):
    INTERNAL = auto()

    JOINED_ROOM = auto()
    INVITED_ROOM = auto()
    LEFT_ROOM = auto()

    TIMELINE = auto()
    STATE = auto()
    EPHEMERAL = auto()
    ACCOUNT_DATA = auto()


class InternalEventType(Enum):
    SYNC_STARTED = auto()
    SYNC_ERRORED = auto()
    SYNC_SUCCESSFUL = auto()
    SYNC_STOPPED = auto()

    JOIN = auto()
    PROFILE_CHANGE = auto()
    INVITE = auto()
    DISINVITE = auto()
    LEAVE = auto()
    KICK = auto()
    BAN = auto()
    UNBAN = auto()


class Client(ClientAPI):
    """Client is a high-level wrapper around the client API."""
    store: ClientStore
    global_event_handlers: List[EventHandler]
    event_handlers: Dict[Union[EventType, InternalEventType], List[EventHandler]]
    dispatchers: Dict[Type['Dispatcher'], 'Dispatcher']
    syncing_task: Optional[asyncio.Future]
    ignore_initial_sync: bool
    ignore_first_sync: bool

    def __init__(self, *args, store: ClientStore = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store or MemoryClientStore()
        self.global_event_handlers = []
        self.event_handlers = {}
        self.dispatchers = {}
        self.syncing_task = None
        self.ignore_initial_sync = False
        self.ignore_first_sync = False

    def on(self, var: Union[EventHandler, EventType, InternalEventType]
           ) -> Union[EventHandler, Callable[[EventHandler], EventHandler]]:
        """
        Add a new event handler. This method is for decorator usage.
        Use :meth:`add_event_handler` if you don't use a decorator.

        Args:
            var: Either the handler function or the event type to handle.

        Returns:
            If ``var`` was the handler function, the handler function is returned.

            If ``var`` was an event type, a function that takes the handler function as an argument
            is returned.

        Examples:
            >>> client = Client(...)
            >>> @client.on(EventType.ROOM_MESSAGE)
            >>> def handler(event: MessageEvent) -> None:
            ...     pass
        """
        if isinstance(var, (EventType, InternalEventType)):
            def decorator(func: EventHandler) -> EventHandler:
                self.add_event_handler(var, func)
                return func

            return decorator
        else:
            self.add_event_handler(EventType.ALL, var)
            return var

    def add_dispatcher(self, dispatcher_type: Type['Dispatcher']) -> None:
        if dispatcher_type in self.dispatchers:
            return
        self.dispatchers[dispatcher_type] = dispatcher_type(self)
        self.dispatchers[dispatcher_type].register()

    def remove_dispatcher(self, dispatcher_type: Type['Dispatcher']) -> None:
        if dispatcher_type not in self.dispatchers:
            return
        self.dispatchers[dispatcher_type].unregister()
        del self.dispatchers[dispatcher_type]

    def add_event_handler(self, event_type: Union[InternalEventType, EventType],
                          handler: EventHandler) -> None:
        """
        Add a new event handler.

        Args:
            event_type: The event type to add. If not specified, the handler will be called for all
                event types.
            handler: The handler function to add.
        """
        if not isinstance(event_type, (EventType, InternalEventType)):
            raise ValueError("Invalid event type")
        if event_type == EventType.ALL:
            self.global_event_handlers.append(handler)
        else:
            self.event_handlers.setdefault(event_type, []).append(handler)

    def remove_event_handler(self, event_type: Union[EventType, InternalEventType],
                             handler: EventHandler) -> None:
        """
        Remove an event handler.

        Args:
            handler: The handler function to remove.
            event_type: The event type to remove the handler function from.
        """
        if not isinstance(event_type, (EventType, InternalEventType)):
            raise ValueError("Invalid event type")
        try:
            if event_type == EventType.ALL:
                self.global_event_handlers.remove(handler)
            else:
                handlers = self.event_handlers[event_type]
                handlers.remove(handler)
                if len(handlers) == 0:
                    del self.event_handlers[event_type]
        except (KeyError, ValueError):
            pass

    async def dispatch_event(self, event: Event, source: SyncStream) -> None:
        """
        Send the given event to all applicable event handlers.

        Args:
            event: The event to send.
            source: The sync stream the event was received in.
        """
        if isinstance(event, MessageEvent):
            event.content.trim_reply_fallback()
        if event.type.is_state and event.state_key is None:
            self.log.debug(f"Not sending {event.event_id} to handlers: expected state_key.")
            return
        elif event.type.is_account_data and not source & SyncStream.ACCOUNT_DATA:
            self.log.debug(f"Not sending {event.event_id} to handlers: got account_data event "
                           f"type in non-account_data sync stream.")
            return
        elif event.type.is_ephemeral and not source & SyncStream.EPHEMERAL:
            self.log.debug(f"Not sending {event.event_id} to handlers: got ephemeral event "
                           f"type in non-ephemeral sync stream.")
            return

        setattr(event, "source", source)
        await self.dispatch_manual_event(event.type, event, include_global_handlers=True)

    async def dispatch_manual_event(self, event_type: Union[EventType, InternalEventType],
                                    data: Any, include_global_handlers: bool = False) -> None:
        handlers = self.event_handlers.get(event_type, [])
        if include_global_handlers:
            handlers = self.global_event_handlers + handlers
        for handler in handlers:
            try:
                await handler(data)
            except Exception:
                self.log.exception("Failed to run handler")

    def dispatch_internal_event(self, event_type: InternalEventType, **kwargs: Any
                                ) -> Awaitable[None]:
        kwargs["source"] = SyncStream.INTERNAL
        return self.dispatch_manual_event(event_type, kwargs,
                                          include_global_handlers=False)

    def handle_sync(self, data: JSON) -> None:
        """
        Handle a /sync object.

        Args:
            data: The data from a /sync request.
        """
        rooms = data.get("rooms", {})
        for room_id, room_data in rooms.get("join", {}).items():
            for raw_event in room_data.get("state", {}).get("events", []):
                raw_event["room_id"] = room_id
                asyncio.ensure_future(
                    self.dispatch_event(StateEvent.deserialize(raw_event),
                                        source=SyncStream.JOINED_ROOM | SyncStream.STATE),
                    loop=self.loop)

            for raw_event in room_data.get("timeline", {}).get("events", []):
                raw_event["room_id"] = room_id
                asyncio.ensure_future(
                    self.dispatch_event(Event.deserialize(raw_event),
                                        source=SyncStream.JOINED_ROOM | SyncStream.TIMELINE),
                    loop=self.loop)
        for room_id, room_data in rooms.get("invite", {}).items():
            events: List[Dict[str, Any]] = room_data.get("invite_state", {}).get("events", [])
            for raw_event in events:
                raw_event["room_id"] = room_id
            raw_invite = next(raw_event for raw_event in events
                              if raw_event.get("type", "") == "m.room.member"
                              and raw_event.get("state_key", "") == self.mxid)
            # These aren't required by the spec, so make sure they're set
            raw_invite.setdefault("event_id", None)
            raw_invite.setdefault("origin_server_ts", int(time() * 1000))

            invite = StateEvent.deserialize(raw_invite)
            invite.unsigned.invite_room_state = [StrippedStateEvent.deserialize(raw_event)
                                                 for raw_event in events
                                                 if raw_event != raw_invite]
            asyncio.ensure_future(
                self.dispatch_event(invite, source=SyncStream.INVITED_ROOM | SyncStream.STATE),
                loop=self.loop)
        for room_id, room_data in rooms.get("leave", {}).items():
            for raw_event in room_data.get("timeline", {}).get("events", []):
                if "state_key" in raw_event:
                    raw_event["room_id"] = room_id
                    asyncio.ensure_future(
                        self.dispatch_event(StateEvent.deserialize(raw_event),
                                            source=SyncStream.LEFT_ROOM | SyncStream.TIMELINE),
                        loop=self.loop)

    def start(self, filter_data: Optional[Union[FilterID, Filter]]) -> asyncio.Future:
        """
        Start syncing with the server. Can be stopped with :meth:`stop`.

        Args:
            filter_data: The filter data or filter ID to use for syncing.
        """
        if self.syncing_task is not None:
            self.syncing_task.cancel()
        self.syncing_task = asyncio.ensure_future(self._try_start(filter_data), loop=self.loop)
        return self.syncing_task

    async def _try_start(self, filter_data: Optional[Union[FilterID, Filter]]) -> None:
        try:
            if isinstance(filter_data, Filter):
                filter_data = await self.create_filter(filter_data)
            await self._start(filter_data)
        except asyncio.CancelledError:
            self.log.debug("Syncing cancelled")
        except Exception as e:
            self.log.exception("Fatal error while syncing")
            await self.dispatch_internal_event(InternalEventType.SYNC_STOPPED, error=e)
            return
        else:
            self.log.debug("Syncing stopped")
        await self.dispatch_internal_event(InternalEventType.SYNC_STOPPED, error=None)

    async def _start(self, filter_id: Optional[FilterID]) -> None:
        fail_sleep = 5
        is_first = True

        self.log.debug("Starting syncing")
        await self.dispatch_internal_event(InternalEventType.SYNC_STARTED)
        while True:
            try:
                data = await self.sync(since=self.store.next_batch, filter_id=filter_id)
                fail_sleep = 5
            except (asyncio.CancelledError, MUnknownToken):
                raise
            except Exception as e:
                self.log.exception(f"Sync request errored, waiting {fail_sleep}"
                                   " seconds before continuing")
                await self.dispatch_internal_event(InternalEventType.SYNC_ERRORED, error=e,
                                                   sleep_for=fail_sleep)
                await asyncio.sleep(fail_sleep, loop=self.loop)
                if fail_sleep < 320:
                    fail_sleep *= 2
                continue

            is_initial = not self.store.next_batch
            data["net.maunium.mautrix"] = {
                "is_initial": is_initial,
                "is_first": is_first,
            }
            self.store.next_batch = data.get("next_batch")
            await self.dispatch_internal_event(InternalEventType.SYNC_SUCCESSFUL, data=data)
            if (self.ignore_first_sync and is_first) or (self.ignore_initial_sync and is_initial):
                is_first = False
                continue
            is_first = False
            try:
                self.handle_sync(data)
            except Exception:
                self.log.exception("Sync handling errored")

    def stop(self) -> None:
        """
        Stop a sync started with :meth:`start`.
        """
        if self.syncing_task:
            self.syncing_task.cancel()
            self.syncing_task = None
