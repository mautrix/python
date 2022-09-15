# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable, Callable, Type, TypeVar
from abc import ABC, abstractmethod
from contextlib import suppress
from enum import Enum, Flag, auto
import asyncio
import time

from mautrix.errors import MUnknownToken
from mautrix.types import (
    JSON,
    AccountDataEvent,
    BaseMessageEventContentFuncs,
    DeviceLists,
    DeviceOTKCount,
    EphemeralEvent,
    Event,
    EventType,
    Filter,
    FilterID,
    GenericEvent,
    MessageEvent,
    PresenceState,
    SerializerError,
    StateEvent,
    StrippedStateEvent,
    SyncToken,
    ToDeviceEvent,
    UserID,
)
from mautrix.util.logging import TraceLogger

from . import dispatcher
from .state_store import MemorySyncStore, SyncStore

EventHandler = Callable[[Event], Awaitable[None]]

T = TypeVar("T", bound=Event)


class SyncStream(Flag):
    INTERNAL = auto()

    JOINED_ROOM = auto()
    INVITED_ROOM = auto()
    LEFT_ROOM = auto()

    TIMELINE = auto()
    STATE = auto()
    EPHEMERAL = auto()
    ACCOUNT_DATA = auto()
    TO_DEVICE = auto()


class InternalEventType(Enum):
    SYNC_STARTED = auto()
    SYNC_ERRORED = auto()
    SYNC_SUCCESSFUL = auto()
    SYNC_STOPPED = auto()

    JOIN = auto()
    PROFILE_CHANGE = auto()
    INVITE = auto()
    REJECT_INVITE = auto()
    DISINVITE = auto()
    LEAVE = auto()
    KICK = auto()
    BAN = auto()
    UNBAN = auto()

    DEVICE_LISTS = auto()
    DEVICE_OTK_COUNT = auto()


class Syncer(ABC):
    loop: asyncio.AbstractEventLoop
    log: TraceLogger
    mxid: UserID

    global_event_handlers: list[tuple[EventHandler, bool]]
    event_handlers: dict[EventType | InternalEventType, list[tuple[EventHandler, bool]]]
    dispatchers: dict[Type[dispatcher.Dispatcher], dispatcher.Dispatcher]
    syncing_task: asyncio.Task | None
    ignore_initial_sync: bool
    ignore_first_sync: bool
    presence: PresenceState

    sync_store: SyncStore

    def __init__(self, sync_store: SyncStore) -> None:
        self.global_event_handlers = []
        self.event_handlers = {}
        self.dispatchers = {}
        self.syncing_task = None
        self.ignore_initial_sync = False
        self.ignore_first_sync = False
        self.presence = PresenceState.ONLINE

        self.sync_store = sync_store or MemorySyncStore()

    def on(
        self, var: EventHandler | EventType | InternalEventType
    ) -> EventHandler | Callable[[EventHandler], EventHandler]:
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
            >>> from mautrix.client import Client
            >>> cli = Client(...)
            >>> @cli.on(EventType.ROOM_MESSAGE)
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

    def add_dispatcher(self, dispatcher_type: Type[dispatcher.Dispatcher]) -> None:
        if dispatcher_type in self.dispatchers:
            return
        self.log.debug(f"Enabling {dispatcher_type.__name__}")
        self.dispatchers[dispatcher_type] = dispatcher_type(self)
        self.dispatchers[dispatcher_type].register()

    def remove_dispatcher(self, dispatcher_type: Type[dispatcher.Dispatcher]) -> None:
        if dispatcher_type not in self.dispatchers:
            return
        self.log.debug(f"Disabling {dispatcher_type.__name__}")
        self.dispatchers[dispatcher_type].unregister()
        del self.dispatchers[dispatcher_type]

    def add_event_handler(
        self,
        event_type: InternalEventType | EventType,
        handler: EventHandler,
        wait_sync: bool = False,
    ) -> None:
        """
        Add a new event handler.

        Args:
            event_type: The event type to add. If not specified, the handler will be called for all
                event types.
            handler: The handler function to add.
            wait_sync: Whether or not the handler should be awaited before the next sync request.
        """
        if not isinstance(event_type, (EventType, InternalEventType)):
            raise ValueError("Invalid event type")
        if event_type == EventType.ALL:
            self.global_event_handlers.append((handler, wait_sync))
        else:
            self.event_handlers.setdefault(event_type, []).append((handler, wait_sync))

    def remove_event_handler(
        self, event_type: EventType | InternalEventType, handler: EventHandler
    ) -> None:
        """
        Remove an event handler.

        Args:
            handler: The handler function to remove.
            event_type: The event type to remove the handler function from.
        """
        if not isinstance(event_type, (EventType, InternalEventType)):
            raise ValueError("Invalid event type")
        try:
            handler_list = (
                self.global_event_handlers
                if event_type == EventType.ALL
                else self.event_handlers[event_type]
            )
        except KeyError:
            # No handlers for this event type registered
            return

        # FIXME this is a bit hacky
        with suppress(ValueError):
            handler_list.remove((handler, True))
        with suppress(ValueError):
            handler_list.remove((handler, False))

        if len(handler_list) == 0 and event_type != EventType.ALL:
            del self.event_handlers[event_type]

    def dispatch_event(self, event: Event | None, source: SyncStream) -> list[asyncio.Task]:
        """
        Send the given event to all applicable event handlers.

        Args:
            event: The event to send.
            source: The sync stream the event was received in.
        """
        if event is None:
            return []
        if isinstance(event.content, BaseMessageEventContentFuncs):
            event.content.trim_reply_fallback()
        if getattr(event, "state_key", None) is not None:
            event.type = event.type.with_class(EventType.Class.STATE)
        elif source & SyncStream.EPHEMERAL:
            event.type = event.type.with_class(EventType.Class.EPHEMERAL)
        elif source & SyncStream.ACCOUNT_DATA:
            event.type = event.type.with_class(EventType.Class.ACCOUNT_DATA)
        elif source & SyncStream.TO_DEVICE:
            event.type = event.type.with_class(EventType.Class.TO_DEVICE)
        else:
            event.type = event.type.with_class(EventType.Class.MESSAGE)
        setattr(event, "source", source)
        return self.dispatch_manual_event(event.type, event, include_global_handlers=True)

    async def _catch_errors(self, handler: EventHandler, data: Any) -> None:
        try:
            await handler(data)
        except Exception:
            self.log.exception("Failed to run handler")

    def dispatch_manual_event(
        self,
        event_type: EventType | InternalEventType,
        data: Any,
        include_global_handlers: bool = False,
        force_synchronous: bool = False,
    ) -> list[asyncio.Task]:
        handlers = self.event_handlers.get(event_type, [])
        if include_global_handlers:
            handlers = self.global_event_handlers + handlers
        tasks = []
        for handler, wait_sync in handlers:
            task = asyncio.create_task(self._catch_errors(handler, data))
            if force_synchronous or wait_sync:
                tasks.append(task)
        return tasks

    async def run_internal_event(
        self, event_type: InternalEventType, custom_type: Any = None, **kwargs: Any
    ) -> None:
        kwargs["source"] = SyncStream.INTERNAL
        tasks = self.dispatch_manual_event(
            event_type,
            custom_type if custom_type is not None else kwargs,
            include_global_handlers=False,
        )
        await asyncio.gather(*tasks)

    def dispatch_internal_event(
        self, event_type: InternalEventType, custom_type: Any = None, **kwargs: Any
    ) -> list[asyncio.Task]:
        kwargs["source"] = SyncStream.INTERNAL
        return self.dispatch_manual_event(
            event_type,
            custom_type if custom_type is not None else kwargs,
            include_global_handlers=False,
        )

    def _try_deserialize(self, type: Type[T], data: JSON) -> T | GenericEvent:
        try:
            return type.deserialize(data)
        except SerializerError as e:
            self.log.trace("Deserialization error traceback", exc_info=True)
            self.log.warning(f"Failed to deserialize {data} into {type.__name__}: {e}")
            try:
                return GenericEvent.deserialize(data)
            except SerializerError:
                return None

    def handle_sync(self, data: JSON) -> list[asyncio.Task]:
        """
        Handle a /sync object.

        Args:
            data: The data from a /sync request.
        """
        tasks = []

        otk_count = data.get("device_one_time_keys_count", {})
        tasks += self.dispatch_internal_event(
            InternalEventType.DEVICE_OTK_COUNT,
            custom_type=DeviceOTKCount(
                curve25519=otk_count.get("curve25519", 0),
                signed_curve25519=otk_count.get("signed_curve25519", 0),
            ),
        )

        device_lists = data.get("device_lists", {})
        tasks += self.dispatch_internal_event(
            InternalEventType.DEVICE_LISTS,
            custom_type=DeviceLists(
                changed=device_lists.get("changed", []),
                left=device_lists.get("left", []),
            ),
        )

        for raw_event in data.get("account_data", {}).get("events", []):
            tasks += self.dispatch_event(
                self._try_deserialize(AccountDataEvent, raw_event), source=SyncStream.ACCOUNT_DATA
            )
        for raw_event in data.get("ephemeral", {}).get("events", []):
            tasks += self.dispatch_event(
                self._try_deserialize(EphemeralEvent, raw_event), source=SyncStream.EPHEMERAL
            )
        for raw_event in data.get("to_device", {}).get("events", []):
            tasks += self.dispatch_event(
                self._try_deserialize(ToDeviceEvent, raw_event), source=SyncStream.TO_DEVICE
            )

        rooms = data.get("rooms", {})
        for room_id, room_data in rooms.get("join", {}).items():
            for raw_event in room_data.get("state", {}).get("events", []):
                raw_event["room_id"] = room_id
                tasks += self.dispatch_event(
                    self._try_deserialize(StateEvent, raw_event),
                    source=SyncStream.JOINED_ROOM | SyncStream.STATE,
                )

            for raw_event in room_data.get("timeline", {}).get("events", []):
                raw_event["room_id"] = room_id
                tasks += self.dispatch_event(
                    self._try_deserialize(Event, raw_event),
                    source=SyncStream.JOINED_ROOM | SyncStream.TIMELINE,
                )
        for room_id, room_data in rooms.get("invite", {}).items():
            events: list[dict[str, JSON]] = room_data.get("invite_state", {}).get("events", [])
            for raw_event in events:
                raw_event["room_id"] = room_id
            raw_invite = next(
                raw_event
                for raw_event in events
                if raw_event.get("type", "") == "m.room.member"
                and raw_event.get("state_key", "") == self.mxid
            )
            # These aren't required by the spec, so make sure they're set
            raw_invite.setdefault("event_id", None)
            raw_invite.setdefault("origin_server_ts", int(time.time() * 1000))

            invite = self._try_deserialize(StateEvent, raw_invite)
            invite.unsigned.invite_room_state = [
                self._try_deserialize(StrippedStateEvent, raw_event)
                for raw_event in events
                if raw_event != raw_invite
            ]
            tasks += self.dispatch_event(invite, source=SyncStream.INVITED_ROOM | SyncStream.STATE)
        for room_id, room_data in rooms.get("leave", {}).items():
            for raw_event in room_data.get("timeline", {}).get("events", []):
                if "state_key" in raw_event:
                    raw_event["room_id"] = room_id
                    tasks += self.dispatch_event(
                        self._try_deserialize(StateEvent, raw_event),
                        source=SyncStream.LEFT_ROOM | SyncStream.TIMELINE,
                    )
        return tasks

    def start(self, filter_data: FilterID | Filter | None) -> asyncio.Future:
        """
        Start syncing with the server. Can be stopped with :meth:`stop`.

        Args:
            filter_data: The filter data or filter ID to use for syncing.
        """
        if self.syncing_task is not None:
            self.syncing_task.cancel()
        self.syncing_task = asyncio.create_task(self._try_start(filter_data))
        return self.syncing_task

    async def _try_start(self, filter_data: FilterID | Filter | None) -> None:
        try:
            if isinstance(filter_data, Filter):
                filter_data = await self.create_filter(filter_data)
            await self._start(filter_data)
        except asyncio.CancelledError:
            self.log.debug("Syncing cancelled")
        except Exception as e:
            self.log.critical("Fatal error while syncing", exc_info=True)
            await self.run_internal_event(InternalEventType.SYNC_STOPPED, error=e)
            return
        except BaseException as e:
            self.log.warning(
                f"Syncing stopped with unexpected {e.__class__.__name__}", exc_info=True
            )
            raise
        else:
            self.log.debug("Syncing stopped without exception")
        await self.run_internal_event(InternalEventType.SYNC_STOPPED, error=None)

    async def _start(self, filter_id: FilterID | None) -> None:
        fail_sleep = 5
        is_first = True

        self.log.debug("Starting syncing")
        next_batch = await self.sync_store.get_next_batch()
        await self.run_internal_event(InternalEventType.SYNC_STARTED)
        timeout = 30
        while True:
            current_batch = next_batch
            start = time.monotonic()
            try:
                data = await self.sync(
                    since=current_batch,
                    filter_id=filter_id,
                    set_presence=self.presence,
                    timeout=timeout * 1000,
                )
            except (asyncio.CancelledError, MUnknownToken):
                raise
            except Exception as e:
                self.log.warning(
                    f"Sync request errored: {type(e).__name__}: {e}, waiting {fail_sleep}"
                    " seconds before continuing"
                )
                await self.run_internal_event(
                    InternalEventType.SYNC_ERRORED, error=e, sleep_for=fail_sleep
                )
                await asyncio.sleep(fail_sleep)
                if fail_sleep < 320:
                    fail_sleep *= 2
                continue
            if fail_sleep != 5:
                self.log.debug("Sync error resolved")
            fail_sleep = 5

            duration = time.monotonic() - start
            if current_batch and duration > timeout + 10:
                self.log.warning(f"Sync request ({current_batch}) took {duration:.3f} seconds")

            is_initial = not current_batch
            data["net.maunium.mautrix"] = {
                "is_initial": is_initial,
                "is_first": is_first,
            }
            next_batch = data.get("next_batch")
            try:
                await self.sync_store.put_next_batch(next_batch)
            except Exception:
                self.log.warning("Failed to store next batch", exc_info=True)
            await self.run_internal_event(InternalEventType.SYNC_SUCCESSFUL, data=data)
            if (self.ignore_first_sync and is_first) or (self.ignore_initial_sync and is_initial):
                is_first = False
                continue
            is_first = False
            self.log.silly(f"Starting sync handling ({current_batch})")
            start = time.monotonic()
            try:
                tasks = self.handle_sync(data)
                await asyncio.gather(*tasks)
            except Exception:
                self.log.exception(f"Sync handling ({current_batch}) errored")
            else:
                self.log.silly(f"Finished sync handling ({current_batch})")
            finally:
                duration = time.monotonic() - start
                if duration > 10:
                    self.log.warning(
                        f"Sync handling ({current_batch}) took {duration:.3f} seconds"
                    )

    def stop(self) -> None:
        """
        Stop a sync started with :meth:`start`.
        """
        if self.syncing_task:
            self.syncing_task.cancel()
            self.syncing_task = None

    @abstractmethod
    async def create_filter(self, filter_params: Filter) -> FilterID:
        pass

    @abstractmethod
    async def sync(
        self,
        since: SyncToken = None,
        timeout: int = 30000,
        filter_id: FilterID = None,
        full_state: bool = False,
        set_presence: PresenceState = None,
    ) -> JSON:
        pass
