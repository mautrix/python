# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, Optional, Dict, List
import asyncio

from mautrix.types import RoomID, UserID, EventID, EventType, StateEvent, StateEventContent, Member

from .api import ClientAPI
from .state_store import StateStore


class StoreUpdatingAPI(ClientAPI):
    state_store: Optional[StateStore]

    def __init__(self, *args, state_store: Optional[StateStore] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_store = state_store

    async def get_state(self, room_id: RoomID) -> List[StateEvent]:
        state = await super().get_state(room_id)
        if self.state_store:
            update_members = self.state_store.set_members(room_id, {
                evt.state_key: evt.content for evt in state
                if evt.type == EventType.ROOM_MEMBER
            })
            await asyncio.gather(update_members,
                                 *[self.state_store.update_state(evt) for evt in state
                                   if evt.type != EventType.ROOM_MEMBER])
        return state

    async def send_state_event(self, room_id: RoomID, event_type: EventType,
                               content: Union[StateEventContent, Dict],
                               state_key: Optional[str] = "", **kwargs) -> EventID:
        event_id = await super().send_state_event(room_id, event_type, content, state_key, **kwargs)
        if self.state_store:
            fake_event = StateEvent(type=event_type, room_id=room_id, event_id=event_id,
                                    sender=self.mxid, state_key=state_key, timestamp=0,
                                    content=content)
            await self.state_store.update_state(fake_event)
        return event_id

    async def get_state_event(self, room_id: RoomID, event_type: EventType,
                              state_key: Optional[str] = None) -> StateEventContent:
        event = await super().get_state_event(room_id, event_type, state_key)
        if self.state_store:
            fake_event = StateEvent(type=event_type, room_id=room_id, event_id=EventID(""),
                                    sender=UserID(""), state_key=state_key, timestamp=0,
                                    content=event)
            await self.state_store.update_state(fake_event)
        return event

    async def get_joined_members(self, room_id: RoomID) -> Dict[UserID, Member]:
        members = await super().get_joined_members(room_id)
        if self.state_store:
            await self.state_store.set_members(room_id, members)
        return members

    async def get_members(self, room_id: RoomID) -> List[StateEvent]:
        member_events = await super().get_members(room_id)
        if self.state_store:
            await self.state_store.set_members(room_id, {evt.state_key: evt.content
                                                         for evt in member_events})
        return member_events
