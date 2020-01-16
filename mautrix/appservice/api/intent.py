# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, Awaitable, List, Tuple, Union, TYPE_CHECKING
from urllib.parse import quote as urllib_quote

from ...api import Method, Path
from ...types import (StateEvent, EventType, StateEventContent, EventID, ContentURI,
                      MessageEventContent, UserID, RoomID, PresenceState,
                      RoomAvatarStateEventContent, RoomNameStateEventContent,
                      RoomTopicStateEventContent, PowerLevelStateEventContent,
                      RoomPinnedEventsStateEventContent, Membership, Member,
                      MemberStateEventContent)
from ...client import ClientAPI
from ...errors import MForbidden, MBadState, MatrixRequestError, IntentError
from ..state_store import StateStore

try:
    import magic
except ImportError:
    magic = None

if TYPE_CHECKING:
    from .appservice import AppServiceAPI


def quote(*args, **kwargs):
    return urllib_quote(*args, **kwargs, safe="")


ENSURE_REGISTERED_METHODS = (
    # Room methods
    ClientAPI.create_room, ClientAPI.add_room_alias, ClientAPI.remove_room_alias,
    ClientAPI.get_room_alias, ClientAPI.get_joined_rooms, ClientAPI.join_room_by_id,
    ClientAPI.join_room, ClientAPI.set_room_directory_visibility, ClientAPI.forget_room,
    # User data methods
    ClientAPI.search_users, ClientAPI.set_displayname, ClientAPI.set_avatar_url,

    ClientAPI.upload_media,
)

ENSURE_JOINED_METHODS = (
    # Room methods
    ClientAPI.invite_user,
    # Event methods
    ClientAPI.get_event, ClientAPI.get_state_event, ClientAPI.get_state,
    ClientAPI.get_joined_members, ClientAPI.get_messages, ClientAPI.send_state_event,
    ClientAPI.send_message_event, ClientAPI.redact,
    ClientAPI.send_receipt, ClientAPI.set_fully_read_marker,
)


class IntentAPI(ClientAPI):
    """
    IntentAPI is a high-level wrapper around the AppServiceAPI that provides many easy-to-use
    functions for accessing the client-server API. It is designed for appservices and will
    automatically handle many things like missing invites using the appservice bot.
    """
    api: 'AppServiceAPI'

    def __init__(self, mxid: UserID, api: 'AppServiceAPI', bot: 'IntentAPI' = None,
                 state_store: StateStore = None):
        super().__init__(mxid, api)
        self.bot = bot
        self.log = api.base_log.getChild("intent")
        self.state_store = state_store

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

    def user(self, user_id: UserID, token: Optional[str] = None) -> 'IntentAPI':
        """
        Get the intent API for a specific user.
        This is just a proxy to :meth:`AppServiceAPI.intent`.

        You should only call this method for the bot user. Calling it with child intent APIs will
        result in a warning log.

        Args:
            user_id: The Matrix ID of the user whose intent API to get.
            token: The access token to use for the Matrix ID.

        Returns:
            The IntentAPI for the given user.
        """
        if not self.bot:
            return self.api.intent(user_id, token)
        else:
            self.log.warning("Called IntentAPI#user() of child intent object.")
            return self.bot.api.intent(user_id, token)

    # region User actions

    async def set_presence(self, presence: PresenceState = PresenceState.ONLINE,
                           status: Optional[str] = None, ignore_cache: bool = False):
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

    async def invite_user(self, room_id: RoomID, user_id: UserID, check_cache: bool = False
                          ) -> None:
        """
        Invite a user to participate in a particular room. They do not start participating in the
        room until they actually join the room.

        Only users currently in the room can invite other users to join that room.

        If the user was invited to the room, the homeserver will add a ``m.room.member`` event to
        the room.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-rooms-roomid-invite>`__

        Args:
            room_id: The ID of the room to which to invite the user.
            user_id: The fully qualified user ID of the invitee.
            check_cache: Whether or not the function should be a no-op if the state store says the
                user is already invited.
        """
        try:
            ok_states = (Membership.INVITE, Membership.JOIN)
            do_invite = (not check_cache
                         or self.state_store.get_membership(room_id, user_id) not in ok_states)
            if do_invite:
                await super().invite_user(room_id, user_id)
                self.state_store.invited(room_id, user_id)
        except MatrixRequestError as e:
            if e.errcode != "M_FORBIDDEN":
                raise IntentError(f"Failed to invite {user_id} to {room_id}", e)
            if "is already in the room" in e.message:
                self.state_store.joined(room_id, user_id)

    def set_room_avatar(self, room_id: RoomID, avatar_url: Optional[ContentURI], **kwargs
                        ) -> Awaitable[EventID]:
        return self.send_state_event(room_id, EventType.ROOM_AVATAR,
                                     RoomAvatarStateEventContent(url=avatar_url),
                                     **kwargs)

    def set_room_name(self, room_id: RoomID, name: str, **kwargs) -> Awaitable[EventID]:
        return self.send_state_event(room_id, EventType.ROOM_NAME,
                                     RoomNameStateEventContent(name=name), **kwargs)

    def set_room_topic(self, room_id: RoomID, topic: str, **kwargs) -> Awaitable[EventID]:
        return self.send_state_event(room_id, EventType.ROOM_TOPIC,
                                     RoomTopicStateEventContent(topic=topic), **kwargs)

    async def get_power_levels(self, room_id: RoomID, ignore_cache: bool = False
                               ) -> PowerLevelStateEventContent:
        await self.ensure_joined(room_id)
        if not ignore_cache:
            try:
                levels = self.state_store.get_power_levels(room_id)
            except KeyError:
                levels = None
            if levels:
                return levels
        levels = await self.get_state_event(room_id, EventType.ROOM_POWER_LEVELS)
        self.state_store.set_power_levels(room_id, levels)
        return levels

    async def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent, **kwargs
                               ) -> EventID:
        response = await self.send_state_event(room_id, EventType.ROOM_POWER_LEVELS, content,
                                               **kwargs)
        if response:
            self.state_store.set_power_levels(room_id, content)
        return response

    async def get_pinned_messages(self, room_id: RoomID) -> List[EventID]:
        await self.ensure_joined(room_id)
        content = await self.get_state_event(room_id, EventType.ROOM_PINNED_EVENTS)
        return content["pinned"]

    def set_pinned_messages(self, room_id: RoomID, events: List[EventID], **kwargs) -> Awaitable[
        dict]:
        return self.send_state_event(room_id, EventType.ROOM_PINNED_EVENTS,
                                     RoomPinnedEventsStateEventContent(pinned=events), **kwargs)

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

    async def set_join_rule(self, room_id: RoomID, join_rule: str, **kwargs):
        if join_rule not in ("public", "knock", "invite", "private"):
            raise ValueError(f"Invalid join rule \"{join_rule}\"")
        await self.send_state_event(room_id, EventType.ROOM_JOIN_RULES, {
            "join_rule": join_rule,
        }, **kwargs)

    async def get_room_displayname(self, room_id: RoomID, user_id: UserID, ignore_cache=False
                                   ) -> str:
        return (await self.get_room_member_info(room_id, user_id, ignore_cache)).displayname

    async def get_room_avatar_url(self, room_id: RoomID, user_id: UserID, ignore_cache=False
                                  ) -> str:
        return (await self.get_room_member_info(room_id, user_id, ignore_cache)).avatar_url

    async def get_room_member_info(self, room_id: RoomID, user_id: UserID, ignore_cache=False
                                   ) -> Member:
        member = self.state_store.get_member(room_id, user_id)
        if not member.membership or ignore_cache:
            member = await self.get_state_event(room_id, EventType.ROOM_MEMBER, user_id)
        return member

    async def set_typing(self, room_id: RoomID, is_typing: bool = True, timeout: int = 5000,
                         ignore_cache: bool = False) -> None:
        await self.ensure_joined(room_id)
        if not ignore_cache and is_typing == self.state_store.is_typing(room_id, self.mxid):
            return
        await super().set_typing(room_id, timeout if is_typing else 0)
        self.state_store.set_typing(room_id, self.mxid, is_typing, timeout)

    async def error_and_leave(self, room_id: RoomID, text: Optional[str] = None,
                              html: Optional[str] = None) -> None:
        await self.ensure_joined(room_id)
        await self.send_notice(room_id, text, html=html)
        await self.leave_room(room_id)

    def get_membership(self, room_id: RoomID, user_id: UserID
                       ) -> Awaitable[MemberStateEventContent]:
        return self.get_state_event(room_id, EventType.ROOM_MEMBER, state_key=user_id)

    def set_membership(self, room_id: RoomID, user_id: UserID, membership: Membership,
                       reason: Optional[str] = "", profile: Optional[dict] = None, **kwargs
                       ) -> Awaitable[dict]:
        body = {
            "membership": membership.serialize(),
            "reason": reason
        }
        profile = profile or {}
        if "displayname" in profile:
            body["displayname"] = profile["displayname"]
        if "avatar_url" in profile:
            body["avatar_url"] = profile["avatar_url"]

        return self.send_state_event(room_id, EventType.ROOM_MEMBER, body, state_key=user_id,
                                     **kwargs)

    async def send_message_event(self, room_id: RoomID, event_type: EventType,
                                 content: Union[MessageEventContent, Dict], **kwargs) -> EventID:
        await self._ensure_has_power_level_for(room_id, event_type)

        if self.api.is_real_user and self.api.real_user_content_key:
            content[self.api.real_user_content_key] = True

        return await super().send_message_event(room_id, event_type, content, **kwargs)

    async def send_state_event(self, room_id: RoomID, event_type: EventType,
                               content: Union[StateEventContent, Dict],
                               state_key: Optional[str] = "", **kwargs) -> EventID:
        await self._ensure_has_power_level_for(room_id, event_type)
        return await super().send_state_event(room_id, event_type, content, state_key, **kwargs)

    async def get_state_event(self, room_id: RoomID, event_type: EventType,
                              state_key: Optional[str] = "") -> StateEventContent:
        event = await super().get_state_event(room_id, event_type, state_key)
        self.state_store.update_state(StateEvent(type=event_type, room_id=room_id,
                                                 event_id=EventID(""), sender=UserID(""),
                                                 state_key=state_key, timestamp=0, content=event))
        return event

    async def leave_room(self, room_id: RoomID) -> None:
        if not room_id:
            raise ValueError("Room ID not given")
        await self.ensure_registered()
        try:
            self.state_store.left(room_id, self.mxid)
            await super().leave_room(room_id)
        except MatrixRequestError as e:
            if "not in room" not in e.message:
                raise

    def get_room_memberships(self, room_id: RoomID) -> Awaitable[dict]:
        if not room_id:
            raise ValueError("Room ID not given")
        return self.api.request(Method.GET, Path.rooms[room_id].members)

    def get_room_joined_memberships(self, room_id: RoomID) -> Awaitable[dict]:
        if not room_id:
            raise ValueError("Room ID not given")
        return self.api.request(Method.GET, Path.rooms[room_id].joined_members)

    async def get_room_members(self, room_id: RoomID,
                               allowed_memberships: Tuple[Membership, ...] = (Membership.JOIN,)
                               ) -> List[UserID]:
        if len(allowed_memberships) == 1 and allowed_memberships[0] == Membership.JOIN:
            memberships = await self.get_room_joined_memberships(room_id)
            return list(memberships["joined"].keys())
        memberships = await self.get_room_memberships(room_id)
        return [membership["state_key"] for membership in memberships["chunk"] if
                Membership(membership["content"]["membership"]) in allowed_memberships]

    async def get_state(self, room_id: RoomID) -> List[StateEvent]:
        state = await super().get_state(room_id)
        for event in state:
            self.state_store.update_state(event)
        return state

    async def mark_read(self, room_id: RoomID, event_id: EventID) -> None:
        if self.state_store.get_read(room_id, self.mxid) != event_id:
            await self.set_fully_read_marker(room_id, fully_read=event_id, read_receipt=event_id)
            self.state_store.set_read(room_id, self.mxid, event_id)

    # endregion
    # region Ensure functions

    async def ensure_joined(self, room_id: RoomID, ignore_cache: bool = False) -> None:
        if not room_id:
            raise ValueError("Room ID not given")
        if not ignore_cache and self.state_store.is_joined(room_id, self.mxid):
            return
        await self.ensure_registered()
        try:
            await self.join_room(room_id, max_retries=0)
            self.state_store.joined(room_id, self.mxid)
        except MForbidden as e:
            if not self.bot:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e
            try:
                await self.bot.invite_user(room_id, self.mxid)
                await self.join_room(room_id, max_retries=0)
                self.state_store.joined(room_id, self.mxid)
                return
            except MatrixRequestError as e2:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e2
        except MBadState as e:
            if not self.bot:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e
            try:
                await self.bot.unban_user(room_id, self.mxid)
                await self.bot.invite_user(room_id, self.mxid)
                await self.join_room(room_id, max_retries=0)
                self.state_store.joined(room_id, self.mxid)
                return
            except MatrixRequestError as e2:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e2
        except MatrixRequestError as e:
            raise IntentError(f"Failed to join room {room_id} as {self.mxid}") from e

    def _register(self) -> Awaitable[dict]:
        content = {"username": self.localpart, "type": "m.login.application_service"}
        return self.api.request(Method.POST, Path.register, content)

    async def ensure_registered(self) -> None:
        if self.state_store.is_registered(self.mxid):
            return
        try:
            await self._register()
        except MatrixRequestError as e:
            if e.errcode != "M_USER_IN_USE":
                raise IntentError(f"Failed to register {self.mxid}", e)
                # self.log.exception(f"Failed to register {self.mxid}!")
                # return
        self.state_store.registered(self.mxid)

    async def _ensure_has_power_level_for(self, room_id: RoomID, event_type: EventType) -> None:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")

        if not self.state_store.has_power_levels(room_id):
            await self.get_power_levels(room_id)
        if not self.state_store.has_power_level(room_id, self.mxid, event_type):
            # TODO implement something better
            raise IntentError(f"Power level of {self.mxid} is not enough "
                              f"for {event_type} in {room_id}")
            # self.log.warning(
            #     f"Power level of {self.mxid} is not enough for {event_type} in {room_id}")

    # endregion
