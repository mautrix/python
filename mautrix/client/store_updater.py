# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import asyncio

from mautrix.errors import MNotFound
from mautrix.types import (
    JSON,
    EventID,
    EventType,
    Member,
    Membership,
    MemberStateEventContent,
    RoomAlias,
    RoomID,
    StateEvent,
    StateEventContent,
    SyncToken,
    UserID,
)

from .api import ClientAPI
from .state_store import StateStore


class StoreUpdatingAPI(ClientAPI):
    """
    StoreUpdatingAPI is a wrapper around the medium-level ClientAPI that optionally updates
    a client state store with outgoing state events (after they're successfully sent).
    """

    state_store: StateStore | None

    def __init__(self, *args, state_store: StateStore | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.state_store = state_store

    async def join_room_by_id(
        self,
        room_id: RoomID,
        third_party_signed: JSON = None,
        extra_content: dict[str, JSON] | None = None,
    ) -> RoomID:
        room_id = await super().join_room_by_id(
            room_id, third_party_signed=third_party_signed, extra_content=extra_content
        )
        if room_id and not extra_content and self.state_store:
            await self.state_store.set_membership(room_id, self.mxid, Membership.JOIN)
        return room_id

    async def join_room(
        self,
        room_id_or_alias: RoomID | RoomAlias,
        servers: list[str] | None = None,
        third_party_signed: JSON = None,
        max_retries: int = 4,
    ) -> RoomID:
        room_id = await super().join_room(
            room_id_or_alias, servers, third_party_signed, max_retries
        )
        if room_id and self.state_store:
            await self.state_store.set_membership(room_id, self.mxid, Membership.JOIN)
        return room_id

    async def leave_room(
        self,
        room_id: RoomID,
        extra_content: dict[str, JSON] | None = None,
        raise_not_in_room: bool = False,
    ) -> None:
        await super().leave_room(room_id, extra_content, raise_not_in_room)
        if not extra_content and self.state_store:
            await self.state_store.set_membership(room_id, self.mxid, Membership.LEAVE)

    async def invite_user(
        self,
        room_id: RoomID,
        user_id: UserID,
        extra_content: dict[str, JSON] | None = None,
    ) -> None:
        await super().invite_user(room_id, user_id, extra_content=extra_content)
        if not extra_content and self.state_store:
            await self.state_store.set_membership(room_id, user_id, Membership.INVITE)

    async def kick_user(
        self,
        room_id: RoomID,
        user_id: UserID,
        reason: str = "",
        extra_content: dict[str, JSON] | None = None,
    ) -> None:
        await super().kick_user(room_id, user_id, reason=reason, extra_content=extra_content)
        if not extra_content and self.state_store:
            await self.state_store.set_membership(room_id, user_id, Membership.LEAVE)

    async def ban_user(
        self,
        room_id: RoomID,
        user_id: UserID,
        reason: str = "",
        extra_content: dict[str, JSON] | None = None,
    ) -> None:
        await super().ban_user(room_id, user_id, reason=reason, extra_content=extra_content)
        if not extra_content and self.state_store:
            await self.state_store.set_membership(room_id, user_id, Membership.BAN)

    async def unban_user(self, room_id: RoomID, user_id: UserID) -> None:
        await super().unban_user(room_id, user_id)
        if self.state_store:
            await self.state_store.set_membership(room_id, user_id, Membership.LEAVE)

    async def get_state(self, room_id: RoomID) -> list[StateEvent]:
        state = await super().get_state(room_id)
        if self.state_store:
            update_members = self.state_store.set_members(
                room_id,
                {evt.state_key: evt.content for evt in state if evt.type == EventType.ROOM_MEMBER},
            )
            await asyncio.gather(
                update_members,
                *[
                    self.state_store.update_state(evt)
                    for evt in state
                    if evt.type != EventType.ROOM_MEMBER
                ],
            )
        return state

    async def send_state_event(
        self,
        room_id: RoomID,
        event_type: EventType,
        content: StateEventContent | dict[str, JSON],
        state_key: str = "",
        **kwargs,
    ) -> EventID:
        event_id = await super().send_state_event(
            room_id, event_type, content, state_key, **kwargs
        )
        if self.state_store:
            fake_event = StateEvent(
                type=event_type,
                room_id=room_id,
                event_id=event_id,
                sender=self.mxid,
                state_key=state_key,
                timestamp=0,
                content=content,
            )
            await self.state_store.update_state(fake_event)
        return event_id

    async def get_state_event(
        self, room_id: RoomID, event_type: EventType, state_key: str = ""
    ) -> StateEventContent:
        event = await super().get_state_event(room_id, event_type, state_key)
        if self.state_store:
            fake_event = StateEvent(
                type=event_type,
                room_id=room_id,
                event_id=EventID(""),
                sender=UserID(""),
                state_key=state_key,
                timestamp=0,
                content=event,
            )
            await self.state_store.update_state(fake_event)
        return event

    async def get_joined_members(self, room_id: RoomID) -> dict[UserID, Member]:
        members = await super().get_joined_members(room_id)
        if self.state_store:
            await self.state_store.set_members(room_id, members, only_membership=Membership.JOIN)
        return members

    async def get_members(
        self,
        room_id: RoomID,
        at: SyncToken | None = None,
        membership: Membership | None = None,
        not_membership: Membership | None = None,
    ) -> list[StateEvent]:
        member_events = await super().get_members(room_id, at, membership, not_membership)
        if self.state_store and not_membership != Membership.JOIN:
            await self.state_store.set_members(
                room_id,
                {evt.state_key: evt.content for evt in member_events},
                only_membership=membership,
            )
        return member_events

    async def fill_member_event(
        self,
        room_id: RoomID,
        user_id: UserID,
        content: MemberStateEventContent,
    ) -> MemberStateEventContent | None:
        """
        Fill a membership event content that is going to be sent in :meth:`send_member_event`.

        This is used to set default fields like the displayname and avatar, which are usually set
        by the server in the sugar membership endpoints like /join and /invite, but are not set
        automatically when sending member events manually.

        This implementation in StoreUpdatingAPI will first try to call the default implementation
        (which calls :attr:`fill_member_event_callback`). If that doesn't return anything, this
        will try to get the profile from the current member event, and then fall back to fetching
        the global profile from the server.

        Args:
            room_id: The room where the member event is going to be sent.
            user_id: The user whose membership is changing.
            content: The new member event content.

        Returns:
            The filled member event content.
        """
        callback_content = await super().fill_member_event(room_id, user_id, content)
        if callback_content is not None:
            self.log.trace("Filled new member event for %s using callback", user_id)
            return callback_content

        if content.displayname is None and content.avatar_url is None:
            existing_member = await self.state_store.get_member(room_id, user_id)
            if existing_member is not None:
                self.log.trace(
                    "Found existing member event %s to fill new member event for %s",
                    existing_member,
                    user_id,
                )
                content.displayname = existing_member.displayname
                content.avatar_url = existing_member.avatar_url
                return content

            try:
                profile = await self.get_profile(user_id)
            except MNotFound:
                profile = None
            if profile:
                self.log.trace(
                    "Fetched profile %s to fill new member event of %s", profile, user_id
                )
                content.displayname = profile.displayname
                content.avatar_url = profile.avatar_url
                return content
            else:
                self.log.trace("Didn't find profile info to fill new member event of %s", user_id)
        else:
            self.log.trace(
                "Member event for %s already contains displayname or avatar, not re-filling",
                user_id,
            )
        return None
