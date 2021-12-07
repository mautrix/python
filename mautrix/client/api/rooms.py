# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable, Callable, Iterable
import asyncio

from multidict import CIMultiDict

from mautrix.api import Method, Path
from mautrix.errors import MatrixRequestError, MatrixResponseError, MNotFound, MRoomInUse
from mautrix.types import (
    JSON,
    DirectoryPaginationToken,
    EventID,
    EventType,
    Membership,
    MemberStateEventContent,
    PowerLevelStateEventContent,
    RoomAlias,
    RoomAliasInfo,
    RoomCreatePreset,
    RoomCreateStateEventContent,
    RoomDirectoryResponse,
    RoomDirectoryVisibility,
    RoomID,
    Serializable,
    StateEvent,
    StrippedStateEvent,
    UserID,
)

from .base import BaseClientAPI
from .events import EventMethods


class RoomMethods(EventMethods, BaseClientAPI):
    """
    Methods in section 8 Rooms of the spec. These methods are used for creating rooms, interacting
    with the room directory and using the easy room metadata editing endpoints. Generic state
    setting and sending events are in the :class:`EventMethods` (section 7) module.

    See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#rooms-1>`__
    """

    # region 8.1 Creation
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#creation

    async def create_room(
        self,
        alias_localpart: str | None = None,
        visibility: RoomDirectoryVisibility = RoomDirectoryVisibility.PRIVATE,
        preset: RoomCreatePreset = RoomCreatePreset.PRIVATE,
        name: str | None = None,
        topic: str | None = None,
        is_direct: bool = False,
        invitees: list[UserID] | None = None,
        initial_state: Iterable[StateEvent | StrippedStateEvent | dict[str, JSON]] | None = None,
        room_version: str = None,
        creation_content: RoomCreateStateEventContent | dict[str, JSON] | None = None,
        power_level_override: PowerLevelStateEventContent | dict[str, JSON] | None = None,
    ) -> RoomID:
        """
        Create a new room with various configuration options.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3createroom>`__

        Args:
            alias_localpart: The desired room alias **local part**. If this is included, a room
                alias will be created and mapped to the newly created room. The alias will belong
                on the same homeserver which created the room. For example, if this was set to
                "foo" and sent to the homeserver "example.com" the complete room alias would be
                ``#foo:example.com``.
            visibility: A ``public`` visibility indicates that the room will be shown in the
                published room list. A ``private`` visibility will hide the room from the published
                room list. Defaults to ``private``. **NB:** This should not be confused with
                ``join_rules`` which also uses the word ``public``.
            preset: Convenience parameter for setting various default state events based on a
                preset. Defaults to private (invite-only).
            name: If this is included, an ``m.room.name`` event will be sent into the room to
                indicate the name of the room. See `Room Events`_ for more information on
                ``m.room.name``.
            topic: If this is included, an ``m.room.topic`` event will be sent into the room to
                indicate the topic for the room. See `Room Events`_ for more information on
                ``m.room.topic``.
            is_direct: This flag makes the server set the ``is_direct`` flag on the
                `m.room.member`_ events sent to the users in ``invite`` and ``invite_3pid``. See
                `Direct Messaging`_ for more information.
            invitees: A list of user IDs to invite to the room. This will tell the server to invite
                everyone in the list to the newly created room.
            initial_state: A list of state events to set in the new room. This allows the user to
                override the default state events set in the new room. The expected format of the
                state events are an object with type, state_key and content keys set.

                Takes precedence over events set by ``is_public``, but gets overriden by ``name``
                and ``topic keys``.
            room_version: The room version to set for the room. If not provided, the homeserver
                will use its configured default.
            creation_content: Extra keys, such as ``m.federate``, to be added to the
                ``m.room.create`` event. The server will ignore ``creator`` and ``room_version``.
                Future versions of the specification may allow the server to ignore other keys.
            power_level_override: The power level content to override in the default power level
                event. This object is applied on top of the generated ``m.room.power_levels`` event
                content prior to it being sent to the room. Defaults to overriding nothing.

        Returns:
            The ID of the newly created room.

        Raises:
            MatrixResponseError: If the response does not contain a ``room_id`` field.

        .. _Room Events: https://spec.matrix.org/v1.1/client-server-api/#room-events
        .. _Direct Messaging: https://spec.matrix.org/v1.1/client-server-api/#direct-messaging
        .. _m.room.create: https://spec.matrix.org/v1.1/client-server-api/#mroomcreate
        .. _m.room.member: https://spec.matrix.org/v1.1/client-server-api/#mroommember
        """
        content = {
            "visibility": visibility.value,
            "is_direct": is_direct,
            "preset": preset.value,
        }
        if alias_localpart:
            content["room_alias_name"] = alias_localpart
        if invitees:
            content["invite"] = invitees
        if name:
            content["name"] = name
        if topic:
            content["topic"] = topic
        if initial_state:
            content["initial_state"] = [
                event.serialize() if isinstance(event, Serializable) else event
                for event in initial_state
            ]
        if room_version:
            content["room_version"] = room_version
        if creation_content:
            content["creation_content"] = (
                creation_content.serialize()
                if isinstance(creation_content, Serializable)
                else creation_content
            )
            # Remove keys that the server will ignore anyway
            content["creation_content"].pop("room_version", None)
        if power_level_override:
            content["power_level_content_override"] = (
                power_level_override.serialize()
                if isinstance(power_level_override, Serializable)
                else power_level_override
            )

        resp = await self.api.request(Method.POST, Path.createRoom, content)
        try:
            return resp["room_id"]
        except KeyError:
            raise MatrixResponseError("`room_id` not in response.")

    # endregion
    # region 8.2 Room aliases
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#room-aliases

    async def add_room_alias(
        self, room_id: RoomID, alias_localpart: str, override: bool = False
    ) -> None:
        """
        Create a new mapping from room alias to room ID.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-directory-room-roomalias>`__

        Args:
            room_id: The room ID to set.
            alias_localpart: The localpart of the room alias to set.
            override: Whether or not the alias should be removed and the request retried if the
                server responds with HTTP 409 Conflict
        """
        room_alias = f"#{alias_localpart}:{self.domain}"
        content = {"room_id": room_id}
        try:
            await self.api.request(Method.PUT, Path.directory.room[room_alias], content)
        except MatrixRequestError as e:
            if e.http_status == 409:
                if override:
                    await self.remove_room_alias(alias_localpart)
                    await self.api.request(Method.PUT, Path.directory.room[room_alias], content)
                else:
                    raise MRoomInUse(e.http_status, e.message) from e
            else:
                raise

    async def remove_room_alias(self, alias_localpart: str, raise_404: bool = False) -> None:
        """
        Remove a mapping of room alias to room ID.

        Servers may choose to implement additional access control checks here, for instance that
        room aliases can only be deleted by their creator or server administrator.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#delete-matrix-client-r0-directory-room-roomalias>`__

        Args:
            alias_localpart: The room alias to remove.
            raise_404: Whether 404 errors should be raised as exceptions instead of ignored.
        """
        room_alias = f"#{alias_localpart}:{self.domain}"
        try:
            await self.api.request(Method.DELETE, Path.directory.room[room_alias])
        except MNotFound:
            if raise_404:
                raise
            # else: ignore

    async def resolve_room_alias(self, room_alias: RoomAlias) -> RoomAliasInfo:
        """
        Request the server to resolve a room alias to a room ID.

        The server will use the federation API to resolve the alias if the domain part of the alias
        does not correspond to the server's own domain.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3directoryroomroomalias>`__

        Args:
            room_alias: The room alias.

        Returns:
            The room ID and a list of servers that are aware of the room.
        """
        content = await self.api.request(Method.GET, Path.directory.room[room_alias])
        return RoomAliasInfo.deserialize(content)

    # endregion
    # region 8.4 Room membership
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#room-membership

    async def get_joined_rooms(self) -> list[RoomID]:
        """Get the list of rooms the user is in."""
        content = await self.api.request(Method.GET, Path.joined_rooms)
        try:
            return content["joined_rooms"]
        except KeyError:
            raise MatrixResponseError("`joined_rooms` not in response.")

    # region 8.4.1 Joining rooms
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#joining-rooms

    async def join_room_by_id(
        self,
        room_id: RoomID,
        third_party_signed: JSON = None,
        extra_content: dict[str, Any] | None = None,
    ) -> RoomID:
        """
        Start participating in a room, i.e. join it by its ID.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3roomsroomidjoin>`__

        Args:
            room_id: The ID of the room to join.
            third_party_signed: A signature of an ``m.third_party_invite`` token to prove that this
                user owns a third party identity which has been invited to the room.
            extra_content: Additional properties for the join event content.
                If a non-empty dict is passed, the join event will be created using
                the ``PUT /state/m.room.member/...`` endpoint instead of ``POST /join``.

        Returns:
            The ID of the room the user joined.
        """
        if extra_content:
            await self.send_member_event(
                room_id, self.mxid, Membership.JOIN, extra_content=extra_content
            )
            return room_id
        content = await self.api.request(
            Method.POST,
            Path.rooms[room_id].join,
            {"third_party_signed": third_party_signed} if third_party_signed is not None else None,
        )
        try:
            return content["room_id"]
        except KeyError:
            raise MatrixResponseError("`room_id` not in response.")

    async def join_room(
        self,
        room_id_or_alias: RoomID | RoomAlias,
        servers: list[str] | None = None,
        third_party_signed: JSON = None,
        max_retries: int = 4,
    ) -> RoomID:
        """
        Start participating in a room, i.e. join it by its ID or alias, with an optional list of
        servers to ask about the ID from.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3joinroomidoralias>`__

        Args:
            room_id_or_alias: The ID of the room to join, or an alias pointing to the room.
            servers: A list of servers to ask about the room ID to join. Not applicable for aliases,
                as aliases already contain the necessary server information.
            third_party_signed: A signature of an ``m.third_party_invite`` token to prove that this
                user owns a third party identity which has been invited to the room.
            max_retries: The maximum number of retries. Used to circumvent a Synapse bug with
                accepting invites over federation. 0 means only one join call will be attempted.
                See: `matrix-org/synapse#2807 <https://github.com/matrix-org/synapse/issues/2807>`__

        Returns:
            The ID of the room the user joined.
        """
        max_retries = max(0, max_retries)
        tries = 0
        content = (
            {"third_party_signed": third_party_signed} if third_party_signed is not None else None
        )
        query_params = CIMultiDict()
        for server_name in servers or []:
            query_params.add("server_name", server_name)
        while tries <= max_retries:
            try:
                content = await self.api.request(
                    Method.POST,
                    Path.join[room_id_or_alias],
                    content=content,
                    query_params=query_params,
                )
                break
            except MatrixRequestError:
                tries += 1
                if tries <= max_retries:
                    wait = tries * 10
                    self.log.exception(
                        f"Failed to join room {room_id_or_alias}, retrying in {wait} seconds..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        try:
            return content["room_id"]
        except KeyError:
            raise MatrixResponseError("`room_id` not in response.")

    fill_member_event_callback: Callable[
        [RoomID, UserID, MemberStateEventContent], Awaitable[MemberStateEventContent | None]
    ] | None

    async def fill_member_event(
        self, room_id: RoomID, user_id: UserID, content: MemberStateEventContent
    ) -> MemberStateEventContent | None:
        """
        Fill a membership event content that is going to be sent in :meth:`send_member_event`.

        This is used to set default fields like the displayname and avatar, which are usually set
        by the server in the sugar membership endpoints like /join and /invite, but are not set
        automatically when sending member events manually.

        This default implementation only calls :attr:`fill_member_event_callback`.

        Args:
            room_id: The room where the member event is going to be sent.
            user_id: The user whose membership is changing.
            content: The new member event content.

        Returns:
            The filled member event content.
        """
        if self.fill_member_event_callback is not None:
            return await self.fill_member_event_callback(room_id, user_id, content)
        return None

    async def send_member_event(
        self,
        room_id: RoomID,
        user_id: UserID,
        membership: Membership,
        extra_content: dict[str, JSON] | None = None,
    ) -> EventID:
        """
        Send a membership event manually.

        Args:
            room_id: The room to send the event to.
            user_id: The user whose membership to change.
            membership: The membership status.
            extra_content: Additional content to put in the member event.

        Returns:
            The event ID of the new member event.
        """
        content = MemberStateEventContent(membership=membership)
        for key, value in extra_content.items():
            content[key] = value
        content = await self.fill_member_event(room_id, user_id, content) or content
        return await self.send_state_event(
            room_id, EventType.ROOM_MEMBER, content=content, state_key=user_id
        )

    async def invite_user(
        self, room_id: RoomID, user_id: UserID, extra_content: dict[str, JSON] | None = None
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
            extra_content: Additional properties for the invite event content.
                If a non-empty dict is passed, the invite event will be created using
                the ``PUT /state/m.room.member/...`` endpoint instead of ``POST /invite``.
        """
        if extra_content:
            await self.send_member_event(
                room_id, user_id, Membership.INVITE, extra_content=extra_content
            )
            return
        await self.api.request(
            Method.POST, Path.rooms[room_id].invite, content={"user_id": user_id}
        )

    # endregion
    # region 8.4.2 Leaving rooms
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#leaving-rooms

    async def leave_room(
        self,
        room_id: RoomID,
        extra_content: dict[str, JSON] | None = None,
        raise_not_in_room: bool = False,
    ) -> None:
        """
        Stop participating in a particular room, i.e. leave the room.

        If the user was already in the room, they will no longer be able to see new events in the
        room. If the room requires an invite to join, they will need to be re-invited before they
        can re-join.

        If the user was invited to the room, but had not joined, this call serves to reject the
        invite.

        The user will still be allowed to retrieve history from the room which they were previously
        allowed to see.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3roomsroomidleave>`__

        Args:
            room_id: The ID of the room to leave.
            extra_content: Additional properties for the leave event content.
                If a non-empty dict is passed, the leave event will be created using
                the ``PUT /state/m.room.member/...`` endpoint instead of ``POST /leave``.
            raise_not_in_room: Should errors about the user not being in the room be raised?
        """
        try:
            if extra_content:
                await self.send_member_event(
                    room_id, self.mxid, Membership.LEAVE, extra_content=extra_content
                )
            else:
                await self.api.request(Method.POST, Path.rooms[room_id].leave)
        except MatrixRequestError as e:
            if "not in room" not in e.message or raise_not_in_room:
                raise

    async def forget_room(self, room_id: RoomID) -> None:
        """
        Stop remembering a particular room, i.e. forget it.

        In general, history is a first class citizen in Matrix. After this API is called, however,
        a user will no longer be able to retrieve history for this room. If all users on a
        homeserver forget a room, the room is eligible for deletion from that homeserver.

        If the user is currently joined to the room, they must leave the room before calling this
        API.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3roomsroomidforget>`__

        Args:
            room_id: The ID of the room to forget.
        """
        await self.api.request(Method.POST, Path.rooms[room_id].forget)

    async def kick_user(
        self,
        room_id: RoomID,
        user_id: UserID,
        reason: str = "",
        extra_content: dict[str, JSON] | None = None,
    ) -> None:
        """
        Kick a user from the room.

        The caller must have the required power level in order to perform this operation.

        Kicking a user adjusts the target member's membership state to be ``leave`` with an optional
        ``reason``. Like with other membership changes, a user can directly adjust the target
        member's state by calling :meth:`EventMethods.send_state_event` with
        :attr:`EventType.ROOM_MEMBER` as the event type and the ``user_id`` as the state key.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3roomsroomidkick>`__

        Args:
            room_id: The ID of the room from which the user should be kicked.
            user_id: The fully qualified user ID of the user being kicked.
            reason: The reason the user has been kicked. This will be supplied as the ``reason`` on
                the target's updated `m.room.member`_ event.
            extra_content: Additional properties for the kick event content.
                If a non-empty dict is passed, the kick event will be created using
                the ``PUT /state/m.room.member/...`` endpoint instead of ``POST /kick``.

        .. _m.room.member: https://spec.matrix.org/v1.1/client-server-api/#mroommember
        """
        if extra_content:
            if reason and "reason" not in extra_content:
                extra_content["reason"] = reason
            await self.send_member_event(
                room_id, user_id, Membership.LEAVE, extra_content=extra_content
            )
            return
        await self.api.request(
            Method.POST, Path.rooms[room_id].kick, {"user_id": user_id, "reason": reason}
        )

    # endregion
    # region 8.4.2.1 Banning users in a room
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#banning-users-in-a-room

    async def ban_user(
        self,
        room_id: RoomID,
        user_id: UserID,
        reason: str = "",
        extra_content: dict[str, JSON] | None = None,
    ) -> None:
        """
        Ban a user in the room. If the user is currently in the room, also kick them. When a user is
        banned from a room, they may not join it or be invited to it until they are unbanned. The
        caller must have the required power level in order to perform this operation.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3roomsroomidban>`__

        Args:
            room_id: The ID of the room from which the user should be banned.
            user_id: The fully qualified user ID of the user being banned.
            reason: The reason the user has been kicked. This will be supplied as the ``reason`` on
                the target's updated `m.room.member`_ event.
            extra_content: Additional properties for the ban event content.
                If a non-empty dict is passed, the ban will be created using
                the ``PUT /state/m.room.member/...`` endpoint instead of ``POST /ban``.

        .. _m.room.member: https://spec.matrix.org/v1.1/client-server-api/#mroommember
        """
        if extra_content:
            if reason and "reason" not in extra_content:
                extra_content["reason"] = reason
            await self.send_member_event(
                room_id, user_id, Membership.BAN, extra_content=extra_content
            )
            return
        await self.api.request(
            Method.POST, Path.rooms[room_id].ban, {"user_id": user_id, "reason": reason}
        )

    async def unban_user(self, room_id: RoomID, user_id: UserID) -> None:
        """
        Unban a user from the room. This allows them to be invited to the room, and join if they
        would otherwise be allowed to join according to its join rules. The caller must have the
        required power level in order to perform this operation.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#post_matrixclientv3roomsroomidunban>`__

        Args:
            room_id: The ID of the room from which the user should be unbanned.
            user_id: The fully qualified user ID of the user being banned.
        """
        await self.api.request(Method.POST, Path.rooms[room_id].unban, {"user_id": user_id})

    # endregion

    # endregion
    # region 8.5 Listing rooms
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#listing-rooms

    async def get_room_directory_visibility(self, room_id: RoomID) -> RoomDirectoryVisibility:
        """
        Get the visibility of the room on the server's public room directory.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3directorylistroomroomid>`__

        Args:
            room_id: The ID of the room.

        Returns:
            The visibility of the room in the directory.
        """
        resp = await self.api.request(Method.GET, Path.directory.list.room[room_id])
        try:
            return RoomDirectoryVisibility(resp["visibility"])
        except KeyError:
            raise MatrixResponseError("`visibility` not in response.")
        except ValueError:
            raise MatrixResponseError(
                f"Invalid value for `visibility` in response: {resp['visibility']}"
            )

    async def set_room_directory_visibility(
        self, room_id: RoomID, visibility: RoomDirectoryVisibility
    ) -> None:
        """
        Set the visibility of the room in the server's public room directory.

        Servers may choose to implement additional access control checks here, for instance that
        room visibility can only be changed by the room creator or a server administrator.

        Args:
            room_id: The ID of the room.
            visibility: The new visibility setting for the room.

        .. _API reference: https://spec.matrix.org/v1.1/client-server-api/#put_matrixclientv3directorylistroomroomid
        """
        await self.api.request(
            Method.PUT,
            Path.directory.list.room[room_id],
            {
                "visibility": visibility.value,
            },
        )

    async def get_room_directory(
        self,
        limit: int | None = None,
        server: str | None = None,
        since: DirectoryPaginationToken | None = None,
        search_query: str | None = None,
        include_all_networks: bool | None = None,
        third_party_instance_id: str | None = None,
    ) -> RoomDirectoryResponse:
        """
        Get a list of public rooms from the server's room directory.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3publicrooms>`__

        Args:
            limit: The maximum number of results to return.
            server: The server to fetch the room directory from. Defaults to the user's server.
            since: A pagination token from a previous request, allowing clients to get the next (or
                previous) batch of rooms. The direction of pagination is specified solely by which
                token is supplied, rather than via an explicit flag.
            search_query: A string to search for in the room metadata, e.g. name, topic, canonical
                alias etc.
            include_all_networks: Whether or not to include rooms from all known networks/protocols
                from application services on the homeserver. Defaults to false.
            third_party_instance_id: The specific third party network/protocol to request from the
                homeserver. Can only be used if ``include_all_networks`` is false.

        Returns:
            The relevant pagination tokens, an estimate of the total number of public rooms and the
            paginated chunk of public rooms.
        """
        method = (
            Method.GET
            if (
                search_query is None
                and include_all_networks is None
                and third_party_instance_id is None
            )
            else Method.POST
        )
        content = {}
        if limit is not None:
            content["limit"] = limit
        if since is not None:
            content["since"] = since
        if search_query is not None:
            content["filter"] = {"generic_search_term": search_query}
        if include_all_networks is not None:
            content["include_all_networks"] = include_all_networks
        if third_party_instance_id is not None:
            content["third_party_instance_id"] = third_party_instance_id
        query_params = {"server": server} if server is not None else None

        content = await self.api.request(
            method, Path.publicRooms, content, query_params=query_params
        )

        return RoomDirectoryResponse.deserialize(content)

    # endregion
