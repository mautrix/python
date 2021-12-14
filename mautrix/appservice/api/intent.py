# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable, Iterable
from urllib.parse import quote as urllib_quote

from mautrix import __optional_imports__
from mautrix.api import Method, Path, UnstableClientPath
from mautrix.client import ClientAPI, StoreUpdatingAPI
from mautrix.errors import (
    IntentError,
    MatrixRequestError,
    MBadState,
    MForbidden,
    MNotFound,
    MUserInUse,
)
from mautrix.types import (
    JSON,
    BatchID,
    BatchSendResponse,
    ContentURI,
    EventContent,
    EventID,
    EventType,
    JoinRule,
    JoinRulesStateEventContent,
    Member,
    Membership,
    MessageEvent,
    PowerLevelStateEventContent,
    PresenceState,
    RoomAvatarStateEventContent,
    RoomID,
    RoomNameStateEventContent,
    RoomPinnedEventsStateEventContent,
    RoomTopicStateEventContent,
    StateEvent,
    StateEventContent,
    UserID,
)
from mautrix.util.logging import TraceLogger

from .. import api as as_api
from .. import state_store as ss

try:
    import magic
except ImportError:
    if __optional_imports__:
        raise
    magic = None


def quote(*args, **kwargs):
    return urllib_quote(*args, **kwargs, safe="")


_bridgebot = object()

ENSURE_REGISTERED_METHODS = (
    # Room methods
    ClientAPI.create_room,
    ClientAPI.add_room_alias,
    ClientAPI.remove_room_alias,
    ClientAPI.resolve_room_alias,
    ClientAPI.get_joined_rooms,
    StoreUpdatingAPI.join_room_by_id,
    StoreUpdatingAPI.join_room,
    StoreUpdatingAPI.leave_room,
    ClientAPI.set_room_directory_visibility,
    ClientAPI.forget_room,
    # User data methods
    ClientAPI.search_users,
    ClientAPI.set_displayname,
    ClientAPI.set_avatar_url,
    ClientAPI.upload_media,
    ClientAPI.send_receipt,
    ClientAPI.set_fully_read_marker,
)

ENSURE_JOINED_METHODS = (
    # Room methods
    StoreUpdatingAPI.invite_user,
    # Event methods
    ClientAPI.get_event,
    StoreUpdatingAPI.get_state_event,
    StoreUpdatingAPI.get_state,
    ClientAPI.get_joined_members,
    ClientAPI.get_messages,
    StoreUpdatingAPI.send_state_event,
    ClientAPI.send_message_event,
    ClientAPI.redact,
)

DOUBLE_PUPPET_SOURCE_KEY = "fi.mau.double_puppet_source"


class IntentAPI(StoreUpdatingAPI):
    """
    IntentAPI is a high-level wrapper around the AppServiceAPI that provides many easy-to-use
    functions for accessing the client-server API. It is designed for appservices and will
    automatically handle many things like missing invites using the appservice bot.
    """

    api: as_api.AppServiceAPI
    state_store: ss.ASStateStore
    bot: IntentAPI
    log: TraceLogger

    def __init__(
        self,
        mxid: UserID,
        api: as_api.AppServiceAPI,
        bot: IntentAPI = None,
        state_store: ss.ASStateStore = None,
    ) -> None:
        super().__init__(mxid=mxid, api=api, state_store=state_store)
        self.bot = bot
        self.log = api.base_log.getChild("intent")

        for method in ENSURE_REGISTERED_METHODS:
            method = getattr(self, method.__name__)

            async def wrapper(*args, __self=self, __method=method, **kwargs):
                await __self.ensure_registered()
                return await __method(*args, **kwargs)

            setattr(self, method.__name__, wrapper)

        for method in ENSURE_JOINED_METHODS:
            method = getattr(self, method.__name__)

            async def wrapper(*args, __self=self, __method=method, **kwargs):
                room_id = kwargs.get("room_id", None)
                if not room_id:
                    room_id = args[0]
                await __self.ensure_joined(room_id)
                return await __method(*args, **kwargs)

            setattr(self, method.__name__, wrapper)

    def user(
        self, user_id: UserID, token: str | None = None, base_url: str | None = None
    ) -> IntentAPI:
        """
        Get the intent API for a specific user.
        This is just a proxy to :meth:`AppServiceAPI.intent`.

        You should only call this method for the bot user. Calling it with child intent APIs will
        result in a warning log.

        Args:
            user_id: The Matrix ID of the user whose intent API to get.
            token: The access token to use for the Matrix ID.
            base_url: An optional URL to use for API requests.

        Returns:
            The IntentAPI for the given user.
        """
        if not self.bot:
            return self.api.intent(user_id, token, base_url)
        else:
            self.log.warning("Called IntentAPI#user() of child intent object.")
            return self.bot.api.intent(user_id, token, base_url)

    # region User actions

    async def set_presence(
        self,
        presence: PresenceState = PresenceState.ONLINE,
        status: str | None = None,
        ignore_cache: bool = False,
    ):
        """
        Set the online status of the user.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-presence-userid-status>`__

        Args:
            presence: The online status of the user.
            status: The status message.
            ignore_cache: Whether or not to set presence even if the cache says the presence is
                already set to that value.
        """
        await self.ensure_registered()
        if not ignore_cache and self.state_store.has_presence(self.mxid, status):
            return
        await super().set_presence(presence, status)
        self.state_store.set_presence(self.mxid, status)

    # endregion
    # region Room actions

    async def invite_user(
        self,
        room_id: RoomID,
        user_id: UserID,
        check_cache: bool = False,
        extra_content: dict[str, Any] | None = None,
    ) -> None:
        """
        Invite a user to participate in a particular room. They do not start participating in the
        room until they actually join the room.

        Only users currently in the room can invite other users to join that room.

        If the user was invited to the room, the homeserver will add a `m.room.member`_ event to
        the room.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3roomsroomidinvite>`__

        .. _m.room.member: https://spec.matrix.org/v1.1/client-server-api/#mroommember

        Args:
            room_id: The ID of the room to which to invite the user.
            user_id: The fully qualified user ID of the invitee.
            check_cache: If ``True``, the function will first check the state store, and not do
                         anything if the state store says the user is already invited or joined.
            extra_content: Additional properties for the invite event content.
                If a non-empty dict is passed, the invite event will be created using
                the ``PUT /state/m.room.member/...`` endpoint instead of ``POST /invite``.
        """
        try:
            ok_states = (Membership.INVITE, Membership.JOIN)
            do_invite = not check_cache or (
                await self.state_store.get_membership(room_id, user_id) not in ok_states
            )
            if do_invite:
                await super().invite_user(room_id, user_id, extra_content=extra_content)
                await self.state_store.invited(room_id, user_id)
        except MatrixRequestError as e:
            if e.errcode == "M_FORBIDDEN" and "is already in the room" in e.message:
                await self.state_store.joined(room_id, user_id)
            else:
                raise IntentError(f"Failed to invite {user_id} to {room_id}", e)

    def set_room_avatar(
        self, room_id: RoomID, avatar_url: ContentURI | None, **kwargs
    ) -> Awaitable[EventID]:
        return self.send_state_event(
            room_id, EventType.ROOM_AVATAR, RoomAvatarStateEventContent(url=avatar_url), **kwargs
        )

    def set_room_name(self, room_id: RoomID, name: str, **kwargs) -> Awaitable[EventID]:
        return self.send_state_event(
            room_id, EventType.ROOM_NAME, RoomNameStateEventContent(name=name), **kwargs
        )

    def set_room_topic(self, room_id: RoomID, topic: str, **kwargs) -> Awaitable[EventID]:
        return self.send_state_event(
            room_id, EventType.ROOM_TOPIC, RoomTopicStateEventContent(topic=topic), **kwargs
        )

    async def get_power_levels(
        self, room_id: RoomID, ignore_cache: bool = False
    ) -> PowerLevelStateEventContent:
        await self.ensure_joined(room_id)
        if not ignore_cache:
            levels = await self.state_store.get_power_levels(room_id)
            if levels:
                return levels
        try:
            levels = await self.get_state_event(room_id, EventType.ROOM_POWER_LEVELS)
        except MNotFound:
            levels = PowerLevelStateEventContent()
        await self.state_store.set_power_levels(room_id, levels)
        return levels

    async def set_power_levels(
        self, room_id: RoomID, content: PowerLevelStateEventContent, **kwargs
    ) -> EventID:
        response = await self.send_state_event(
            room_id, EventType.ROOM_POWER_LEVELS, content, **kwargs
        )
        if response:
            await self.state_store.set_power_levels(room_id, content)
        return response

    async def get_pinned_messages(self, room_id: RoomID) -> list[EventID]:
        await self.ensure_joined(room_id)
        try:
            content = await self.get_state_event(room_id, EventType.ROOM_PINNED_EVENTS)
        except MNotFound:
            return []
        return content["pinned"]

    def set_pinned_messages(
        self, room_id: RoomID, events: list[EventID], **kwargs
    ) -> Awaitable[EventID]:
        return self.send_state_event(
            room_id,
            EventType.ROOM_PINNED_EVENTS,
            RoomPinnedEventsStateEventContent(pinned=events),
            **kwargs,
        )

    async def pin_message(self, room_id: RoomID, event_id: EventID) -> None:
        events = await self.get_pinned_messages(room_id)
        if event_id not in events:
            events.append(event_id)
            await self.set_pinned_messages(room_id, events)

    async def unpin_message(self, room_id: RoomID, event_id: EventID):
        events = await self.get_pinned_messages(room_id)
        if event_id in events:
            events.remove(event_id)
            await self.set_pinned_messages(room_id, events)

    async def set_join_rule(self, room_id: RoomID, join_rule: JoinRule, **kwargs):
        await self.send_state_event(
            room_id,
            EventType.ROOM_JOIN_RULES,
            JoinRulesStateEventContent(join_rule=join_rule),
            **kwargs,
        )

    async def get_room_displayname(
        self, room_id: RoomID, user_id: UserID, ignore_cache=False
    ) -> str:
        return (await self.get_room_member_info(room_id, user_id, ignore_cache)).displayname

    async def get_room_avatar_url(
        self, room_id: RoomID, user_id: UserID, ignore_cache=False
    ) -> str:
        return (await self.get_room_member_info(room_id, user_id, ignore_cache)).avatar_url

    async def get_room_member_info(
        self, room_id: RoomID, user_id: UserID, ignore_cache=False
    ) -> Member:
        member = await self.state_store.get_member(room_id, user_id)
        if not member or not member.membership or ignore_cache:
            member = await self.get_state_event(room_id, EventType.ROOM_MEMBER, user_id)
        return member

    async def set_typing(
        self,
        room_id: RoomID,
        is_typing: bool = True,
        timeout: int = 5000,
        ignore_cache: bool = False,
    ) -> None:
        await self.ensure_joined(room_id)
        if not ignore_cache and is_typing == self.state_store.is_typing(room_id, self.mxid):
            return
        await super().set_typing(room_id, timeout if is_typing else 0)
        self.state_store.set_typing(room_id, self.mxid, is_typing, timeout)

    async def error_and_leave(
        self, room_id: RoomID, text: str | None = None, html: str | None = None
    ) -> None:
        await self.ensure_joined(room_id)
        await self.send_notice(room_id, text, html=html)
        await self.leave_room(room_id)

    async def send_message_event(
        self, room_id: RoomID, event_type: EventType, content: EventContent, **kwargs
    ) -> EventID:
        await self._ensure_has_power_level_for(room_id, event_type)

        if self.api.is_real_user and self.api.bridge_name is not None:
            content[DOUBLE_PUPPET_SOURCE_KEY] = self.api.bridge_name

        return await super().send_message_event(room_id, event_type, content, **kwargs)

    async def redact(
        self, room_id: RoomID, event_id: EventID, reason: str | None = None, **kwargs
    ) -> EventID:
        await self._ensure_has_power_level_for(room_id, EventType.ROOM_REDACTION)
        return await super().redact(
            room_id,
            event_id,
            reason,
            extra_content=(
                {DOUBLE_PUPPET_SOURCE_KEY: self.api.bridge_name}
                if self.api.is_real_user and self.api.bridge_name is not None
                else {}
            ),
            **kwargs,
        )

    async def send_state_event(
        self,
        room_id: RoomID,
        event_type: EventType,
        content: StateEventContent | dict[str, JSON],
        state_key: str = "",
        **kwargs,
    ) -> EventID:
        await self._ensure_has_power_level_for(room_id, event_type, state_key=state_key)
        return await super().send_state_event(room_id, event_type, content, state_key, **kwargs)

    async def get_room_members(
        self, room_id: RoomID, allowed_memberships: tuple[Membership, ...] = (Membership.JOIN,)
    ) -> list[UserID]:
        if len(allowed_memberships) == 1 and allowed_memberships[0] == Membership.JOIN:
            memberships = await self.get_joined_members(room_id)
            return list(memberships.keys())
        member_events = await self.get_members(room_id)
        return [
            UserID(evt.state_key)
            for evt in member_events
            if evt.content.membership in allowed_memberships
        ]

    async def mark_read(self, room_id: RoomID, event_id: EventID) -> None:
        if self.state_store.get_read(room_id, self.mxid) != event_id:
            await self.set_fully_read_marker(room_id, fully_read=event_id, read_receipt=event_id)
            self.state_store.set_read(room_id, self.mxid, event_id)

    async def batch_send(
        self,
        room_id: RoomID,
        prev_event_id: EventID,
        *,
        batch_id: BatchID | None = None,
        events: Iterable[MessageEvent],
        state_events_at_start: Iterable[StateEvent] = None,
    ) -> BatchSendResponse:
        """
        Send a batch of historical events into a room. See `MSC2716`_ for more info.

        .. _MSC2716: https://github.com/matrix-org/matrix-doc/pull/2716

        .. versionadded:: v0.12.5

        Args:
            room_id: The room ID to send the events to.
            prev_event_id: The anchor event. The batch will be inserted immediately after this event.
            batch_id: The batch ID for sending a continuation of an earlier batch. If provided,
                      the new batch will be inserted between the prev event and the previous batch.
            events: The events to send.
            state_events_at_start: The state events to send at the start of the batch.
                                   These will be sent as outlier events, which means they won't be
                                   a part of the actual room state.

        Returns:
            All the event IDs generated, plus a batch ID that can be passed back to this method.
        """
        path = UnstableClientPath["org.matrix.msc2716"].rooms[room_id].batch_send
        query = {"prev_event_id": prev_event_id}
        if batch_id:
            query["batch_id"] = batch_id
        resp = await self.api.request(
            Method.POST,
            path,
            query_params=query,
            content={
                "events": [evt.serialize() for evt in events],
                "state_events_at_start": [evt.serialize() for evt in state_events_at_start],
            },
        )
        return BatchSendResponse.deserialize(resp)

    # endregion
    # region Ensure functions

    async def ensure_joined(
        self, room_id: RoomID, ignore_cache: bool = False, bot: IntentAPI | None = _bridgebot
    ) -> bool:
        """
        Ensure the user controlled by this intent is joined to the given room.

        If the user is not in the room and the room is invite-only or the user is banned, this will
        first invite and/or unban the user using the bridge bot account.

        Args:
            room_id: The room to join.
            ignore_cache: Should the Matrix state store be checked first?
                If ``False`` and the store says the user is in the room, no requests will be made.
            bot: An optional override account to use as the bridge bot. This is useful if you know
                the bridge bot is not an admin in the room, but some other ghost user is.

        Returns:
            ``False`` if the cache said the user is already in the room,
            ``True`` if the user was successfully added to the room just now.
        """
        if not room_id:
            raise ValueError("Room ID not given")
        if not ignore_cache and await self.state_store.is_joined(room_id, self.mxid):
            return False
        if bot is _bridgebot:
            bot = self.bot
        if bot is self:
            bot = None
        await self.ensure_registered()
        try:
            await self.join_room(room_id, max_retries=0)
            await self.state_store.joined(room_id, self.mxid)
        except MForbidden as e:
            if not bot:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e
            try:
                await bot.invite_user(room_id, self.mxid)
                await self.join_room(room_id, max_retries=0)
                await self.state_store.joined(room_id, self.mxid)
            except MatrixRequestError as e2:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e2
        except MBadState as e:
            if not bot:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e
            try:
                await bot.unban_user(room_id, self.mxid)
                await bot.invite_user(room_id, self.mxid)
                await self.join_room(room_id, max_retries=0)
                await self.state_store.joined(room_id, self.mxid)
            except MatrixRequestError as e2:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e2
        except MatrixRequestError as e:
            raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e
        return True

    def _register(self) -> Awaitable[dict]:
        content = {
            "username": self.localpart,
            "type": "m.login.application_service",
            "inhibit_login": True,
        }
        query_params = {"kind": "user"}
        return self.api.request(Method.POST, Path.register, content, query_params=query_params)

    async def ensure_registered(self) -> None:
        """
        Ensure the user controlled by this intent has been registered on the homeserver.

        This will always check the state store first, but the ``M_USER_IN_USE`` error will also be
        silently ignored, so it's fine if the state store isn't accurate. However, if using double
        puppeting, the state store should always return ``True`` for those users.
        """
        if await self.state_store.is_registered(self.mxid):
            return
        try:
            await self._register()
        except MUserInUse:
            pass
        except MatrixRequestError as e:
            raise IntentError(f"Failed to register {self.mxid}", e)
        await self.state_store.registered(self.mxid)

    async def _ensure_has_power_level_for(
        self, room_id: RoomID, event_type: EventType, state_key: str = ""
    ) -> None:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")

        if event_type == EventType.ROOM_MEMBER:
            # TODO: if state_key doesn't equal self.mxid, check invite/kick/ban permissions
            return
        if not await self.state_store.has_power_levels_cached(room_id):
            # TODO add option to not try to fetch power levels from server
            await self.get_power_levels(room_id, ignore_cache=True)
        if not await self.state_store.has_power_level(room_id, self.mxid, event_type):
            # TODO implement something better
            raise IntentError(
                f"Power level of {self.mxid} is not enough for {event_type} in {room_id}"
            )
            # self.log.warning(
            #     f"Power level of {self.mxid} is not enough for {event_type} in {room_id}")

    # endregion
