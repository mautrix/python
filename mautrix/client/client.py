from typing import Dict, List, Callable, Union, Optional, Awaitable

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

    async def start(self, since: Optional[SyncToken] = None,
                    filter: Optional[Union[FilterID, Filter]] = None):
        if isinstance(filter, Filter):
            filter = self.create_filter(filter)

        while True:
            data = await self.sync(since=since, filter_id=filter)
