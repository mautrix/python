from typing import Dict, List, Callable, Union, Optional, Awaitable
import asyncio

from ..api import JSON
from .api.types import EventType, Event, FilterID, Filter, SyncToken
from .api import ClientAPI

EventHandler = Callable[[Awaitable[Event]], None]


class Client(ClientAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.global_event_handlers: List[EventHandler] = []
        self.event_handlers: Dict[EventType, EventHandler] = {}

    def on(self, var: Union[EventHandler, EventType]
           ) -> Union[EventHandler, Callable[[EventHandler], EventHandler]]:
        if isinstance(var, EventType):
            def decorator(func: EventHandler) -> EventHandler:
                self.add_event_handler(func, var)
                return func

            return decorator
        self.add_event_handler(var)
        return var

    def add_event_handler(self, handler: EventHandler, event_type: Optional[EventType] = None
                          ) -> None:
        if not isinstance(event_type, EventType):
            self.global_event_handlers.append(handler)
        else:
            self.event_handlers.setdefault(event_type, []).append(handler)

    async def call_handlers(self, event: Event) -> None:
        for handler in self.global_event_handlers + self.event_handlers.get(event.type, []):
            asyncio.ensure_future(handler(event))

    async def handle_sync(self, data: JSON) -> None:
        for room_id, room_data in data.get("rooms", {}).get("join", {}).items():
            for raw_event in room_data.get("state", {}).get("events", []):
                raw_event["room_id"] = room_id
                await self.call_handlers(StateEvent.deserialize(raw_event))

            for raw_event in room_data.get("timeline", {}).get("events", []):
                raw_event["room_id"] = room_id
                await self.call_handlers(Event.deserialize(raw_event))
        pass

    async def start(self, since: Optional[SyncToken] = None,
                    filter: Optional[Union[FilterID, Filter]] = None):
        if isinstance(filter, Filter):
            filter = self.create_filter(filter)

        while True:
            data = await self.sync(since=since, filter_id=filter)
            try:
                await self.handle_sync(data)
            except Exception:
                self.api.log.exception("Sync handling errored")
