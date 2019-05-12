# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Callable, Union, Optional, Awaitable
import asyncio

from ..errors import MUnknownToken
from ..api import JSON
from .api.types import (EventType, MessageEvent, StateEvent, StrippedStateEvent, Event, FilterID,
                        Filter)
from .api import ClientAPI
from .store import ClientStore, MemoryClientStore

EventHandler = Callable[[Event], Awaitable[None]]


class Client(ClientAPI):
    """Client is a high-level wrapper around the client API."""

    def __init__(self, *args, store: ClientStore = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store or MemoryClientStore()
        self.global_event_handlers: List[EventHandler] = []
        self.event_handlers: Dict[EventType, List[EventHandler]] = {}
        self.syncing_task: Optional[asyncio.Task] = None

    def on(self, var: Union[EventHandler, EventType]
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
        if isinstance(var, EventType):
            def decorator(func: EventHandler) -> EventHandler:
                self.add_event_handler(var, func)
                return func

            return decorator
        else:
            self.add_event_handler(EventType.ALL, var)
            return var

    def add_event_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Add a new event handler.

        Args:
            event_type: The event type to add. If not specified, the handler will be called for all
                event types.
            handler: The handler function to add.
        """
        if not isinstance(event_type, EventType):
            raise ValueError("Invalid event type")
        if event_type == EventType.ALL:
            self.global_event_handlers.append(handler)
        else:
            self.event_handlers.setdefault(event_type, []).append(handler)

    def remove_event_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Remove an event handler.

        Args:
            handler: The handler function to remove.
            event_type: The event type to remove the handler function from.
        """
        if not isinstance(event_type, EventType):
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

    async def call_handlers(self, event: Event) -> None:
        """
        Send the given event to all applicable event handlers.

        Args:
            event: The event to send.
        """
        if isinstance(event, MessageEvent):
            event.content.trim_reply_fallback()
        for handler in self.global_event_handlers + self.event_handlers.get(event.type, []):
            try:
                await handler(event)
            except Exception:
                self.log.exception("Failed to run handler")

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
                asyncio.ensure_future(self.call_handlers(StateEvent.deserialize(raw_event)),
                                      loop=self.loop)

            for raw_event in room_data.get("timeline", {}).get("events", []):
                raw_event["room_id"] = room_id
                asyncio.ensure_future(self.call_handlers(Event.deserialize(raw_event)),
                                      loop=self.loop)
        for room_id, room_data in rooms.get("invite", {}).items():
            for raw_event in room_data.get("invite_state", {}).get("events", []):
                raw_event["room_id"] = room_id
                asyncio.ensure_future(self.call_handlers(StrippedStateEvent.deserialize(raw_event)),
                                      loop=self.loop)
        for room_id, room_data in rooms.get("leave", {}).items():
            for raw_event in room_data.get("timeline", {}).get("events", []):
                if "state_key" in raw_event:
                    raw_event["room_id"] = room_id
                    asyncio.ensure_future(self.call_handlers(StateEvent.deserialize(raw_event)),
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
            await self._start(filter_data)
        except asyncio.CancelledError:
            self.log.debug("Syncing stopped")
        except Exception:
            self.log.exception("Fatal error while syncing")

    async def _start(self, filter_data: Optional[Union[FilterID, Filter]] = None) -> None:
        if isinstance(filter_data, Filter):
            filter_data = await self.create_filter(filter_data)

        fail_sleep = 5

        self.log.debug("Starting syncing")
        while True:
            try:
                data = await self.sync(since=self.store.next_batch, filter_id=filter_data)
                fail_sleep = 5
            except (asyncio.CancelledError, MUnknownToken):
                raise
            except Exception:
                self.log.exception(f"Sync request errored, waiting {fail_sleep}"
                                   " seconds before continuing")
                await asyncio.sleep(fail_sleep, loop=self.loop)
                if fail_sleep < 320:
                    fail_sleep *= 2
                continue

            self.store.next_batch = data.get("next_batch")
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
