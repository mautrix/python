# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import ClassVar
from abc import ABC, abstractmethod

from mautrix.types import Event, EventType, Membership, StateEvent

from . import syncer


class Dispatcher(ABC):
    client: syncer.Syncer

    def __init__(self, client: syncer.Syncer) -> None:
        self.client = client

    @abstractmethod
    def register(self) -> None:
        pass

    @abstractmethod
    def unregister(self) -> None:
        pass


class SimpleDispatcher(Dispatcher, ABC):
    event_type: ClassVar[EventType]

    def register(self) -> None:
        self.client.add_event_handler(self.event_type, self.handle)

    def unregister(self) -> None:
        self.client.remove_event_handler(self.event_type, self.handle)

    @abstractmethod
    async def handle(self, evt: Event) -> None:
        pass


class MembershipEventDispatcher(SimpleDispatcher):
    event_type = EventType.ROOM_MEMBER

    async def handle(self, evt: StateEvent) -> None:
        if evt.type != EventType.ROOM_MEMBER:
            return

        if evt.content.membership == Membership.JOIN:
            if evt.prev_content.membership != Membership.JOIN:
                change_type = syncer.InternalEventType.JOIN
            else:
                change_type = syncer.InternalEventType.PROFILE_CHANGE
        elif evt.content.membership == Membership.INVITE:
            change_type = syncer.InternalEventType.INVITE
        elif evt.content.membership == Membership.LEAVE:
            if evt.prev_content.membership == Membership.BAN:
                change_type = syncer.InternalEventType.UNBAN
            elif evt.prev_content.membership == Membership.INVITE:
                if evt.state_key == evt.sender:
                    change_type = syncer.InternalEventType.REJECT_INVITE
                else:
                    change_type = syncer.InternalEventType.DISINVITE
            elif evt.state_key == evt.sender:
                change_type = syncer.InternalEventType.LEAVE
            else:
                change_type = syncer.InternalEventType.KICK
        elif evt.content.membership == Membership.BAN:
            change_type = syncer.InternalEventType.BAN
        else:
            return

        self.client.dispatch_manual_event(change_type, evt)
