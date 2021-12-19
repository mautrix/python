# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Awaitable

from mautrix.api import Method, Path
from mautrix.errors import MatrixResponseError
from mautrix.types import (
    JSON,
    BaseFileInfo,
    ContentURI,
    Event,
    EventContent,
    EventID,
    EventType,
    FilterID,
    Format,
    ImageInfo,
    MediaMessageEventContent,
    Member,
    Membership,
    MessageEventContent,
    MessageType,
    Obj,
    PaginatedMessages,
    PaginationDirection,
    PresenceState,
    ReactionEventContent,
    RelatesTo,
    RelationType,
    RoomID,
    Serializable,
    SerializerError,
    StateEvent,
    StateEventContent,
    SyncToken,
    TextMessageEventContent,
    UserID,
)
from mautrix.types.event.state import state_event_content_map
from mautrix.util.formatter import parse_html

from .base import BaseClientAPI


class EventMethods(BaseClientAPI):
    """
    Methods in section 8 Events of the spec. Includes ``/sync``'ing, getting messages and state,
    setting state, sending messages and redacting messages. See also: `Events API reference`_

    .. _Events API reference:
        https://spec.matrix.org/v1.1/client-server-api/#events
    """

    # region 8.4 Syncing
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#syncing

    def sync(
        self,
        since: SyncToken | None = None,
        timeout: int = 30000,
        filter_id: FilterID | None = None,
        full_state: bool = False,
        set_presence: PresenceState | None = None,
    ) -> Awaitable[JSON]:
        """
        Perform a sync request. See also: `/sync API reference`_

        This method doesn't parse the response at all.
        You should use :class:`mautrix.client.Syncer` to parse sync responses and dispatch the data
        into event handlers. :class:`mautrix.client.Client` includes ``Syncer``.

        Args:
            since (str): Optional. A token which specifies where to continue a sync from.
            timeout (int): Optional. The time in milliseconds to wait.
            filter_id (int): A filter ID.
            full_state (bool): Return the full state for every room the user has joined
                Defaults to false.
            set_presence (str): Should the client be marked as "online" or" offline"

        .. _/sync API reference:
            https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3sync
        """
        request = {"timeout": timeout}
        if since:
            request["since"] = str(since)
        if filter_id:
            request["filter"] = str(filter_id)
        if full_state:
            request["full_state"] = "true" if full_state else "false"
        if set_presence:
            request["set_presence"] = str(set_presence)
        return self.api.request(
            Method.GET, Path.sync, query_params=request, retry_count=0, metrics_method="sync"
        )

    # endregion
    # region 7.5 Getting events for a room
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#getting-events-for-a-room

    async def get_event(self, room_id: RoomID, event_id: EventID) -> Event:
        """
        Get a single event based on ``room_id``/``event_id``. You must have permission to retrieve
        this event e.g. by being a member in the room for this event.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3roomsroomideventeventid>`__

        Args:
            room_id: The ID of the room the event is in.
            event_id: The event ID to get.

        Returns:
            The event.
        """
        content = await self.api.request(
            Method.GET, Path.rooms[room_id].event[event_id], metrics_method="getEvent"
        )
        try:
            return Event.deserialize(content)
        except SerializerError as e:
            raise MatrixResponseError("Invalid event in response") from e

    async def get_state_event(
        self,
        room_id: RoomID,
        event_type: EventType,
        state_key: str = "",
    ) -> StateEventContent:
        """
        Looks up the contents of a state event in a room. If the user is joined to the room then the
        state is taken from the current state of the room. If the user has left the room then the
        state is taken from the state of the room when they left.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3roomsroomidstateeventtypestatekey>`__

        Args:
            room_id: The ID of the room to look up the state in.
            event_type: The type of state to look up.
            state_key: The key of the state to look up. Defaults to empty string.

        Returns:
            The state event.
        """
        content = await self.api.request(
            Method.GET,
            Path.rooms[room_id].state[event_type][state_key],
            metrics_method="getStateEvent",
        )
        try:
            return state_event_content_map[event_type].deserialize(content)
        except KeyError:
            return Obj(**content)
        except SerializerError as e:
            raise MatrixResponseError("Invalid state event in response") from e

    async def get_state(self, room_id: RoomID) -> list[StateEvent]:
        """
        Get the state events for the current state of a room.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3roomsroomidstate>`__

        Args:
            room_id: The ID of the room to look up the state for.

        Returns:
            A list of state events with the most recent of each event_type/state_key pair.
        """
        content = await self.api.request(
            Method.GET, Path.rooms[room_id].state, metrics_method="getState"
        )
        try:
            return [StateEvent.deserialize(event) for event in content]
        except SerializerError as e:
            raise MatrixResponseError("Invalid state events in response") from e

    async def get_members(
        self,
        room_id: RoomID,
        at: SyncToken | None = None,
        membership: Membership | None = None,
        not_membership: Membership | None = None,
    ) -> list[StateEvent]:
        """
        Get the list of members for a room.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3roomsroomidmembers>`__

        Args:
            room_id: The ID of the room to get the member events for.
            at: The point in time (pagination token) to return members for in the room. This token
                can be obtained from a ``prev_batch`` token returned for each room by the sync API.
                Defaults to the current state of the room, as determined by the server.
            membership: The kind of membership to filter for. Defaults to no filtering if
                unspecified. When specified alongside ``not_membership``, the two parameters create
                an 'or' condition: either the ``membership`` is the same as membership or is not the
                same as ``not_membership``.
            not_membership: The kind of membership to exclude from the results. Defaults to no
                filtering if unspecified.

        Returns:
            A list of most recent member events for each user.
        """
        query = {}
        if at:
            query["at"] = at
        if membership:
            query["membership"] = membership.value
        if not_membership:
            query["not_membership"] = not_membership.value
        content = await self.api.request(
            Method.GET,
            Path.rooms[room_id].members,
            query_params=query,
            metrics_method="getMembers",
        )
        try:
            return [StateEvent.deserialize(event) for event in content["chunk"]]
        except KeyError:
            raise MatrixResponseError("`chunk` not in response.")
        except SerializerError as e:
            raise MatrixResponseError("Invalid state events in response") from e

    async def get_joined_members(self, room_id: RoomID) -> dict[UserID, Member]:
        """
        Get a user ID -> member info map for a room. The current user must be in the room for it to
        work, unless it is an Application Service in which case any of the AS's users must be in the
        room. This API is primarily for Application Services and should be faster to respond than
        `/members`_ as it can be implemented more efficiently on the server.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3roomsroomidjoined_members>`__

        Args:
            room_id: The ID of the room to get the members of.

        Returns:
            A dictionary from user IDs to Member info objects.

        .. _/members:
            https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3roomsroomidmembers
        """
        content = await self.api.request(
            Method.GET, Path.rooms[room_id].joined_members, metrics_method="getJoinedMembers"
        )
        try:
            return {
                user_id: Member(
                    membership=Membership.JOIN,
                    displayname=member.get("display_name", ""),
                    avatar_url=member.get("avatar_url", ""),
                )
                for user_id, member in content["joined"].items()
            }
        except KeyError:
            raise MatrixResponseError("`joined` not in response.")
        except SerializerError as e:
            raise MatrixResponseError("Invalid member objects in response") from e

    async def get_messages(
        self,
        room_id: RoomID,
        direction: PaginationDirection,
        from_token: SyncToken,
        to_token: SyncToken | None = None,
        limit: int | None = None,
        filter_json: str | None = None,
    ) -> PaginatedMessages:
        """
        Get a list of message and state events for a room. Pagination parameters are used to
        paginate history in the room.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3roomsroomidmessages>`__

        Args:
            room_id: The ID of the room to get events from.
            direction: The direction to return events from.
            from_token: The token to start returning events from. This token can be obtained from a
                ``prev_batch`` token returned for each room by the `sync endpoint`_, or from a
                ``start`` or ``end`` token returned by a previous request to this endpoint.
            to_token: The token to stop returning events at.
            limit: The maximum number of events to return. Defaults to 10.
            filter_json: A JSON RoomEventFilter_ to filter returned events with.

        Returns:

        .. _RoomEventFilter:
            https://spec.matrix.org/v1.1/client-server-api/#filtering
        .. _sync endpoint:
            https://spec.matrix.org/v1.1/client-server-api/#get_matrixclientv3sync
        """
        query_params = {
            "from": from_token,
            "dir": direction.value,
            "to": to_token,
            "limit": str(limit) if limit else None,
            "filter_json": filter_json,
        }
        content = await self.api.request(
            Method.GET,
            Path.rooms[room_id].messages,
            query_params=query_params,
            metrics_method="getMessages",
        )
        try:
            return PaginatedMessages(
                content["start"],
                content["end"],
                [Event.deserialize(event) for event in content["chunk"]],
            )
        except KeyError:
            if "start" not in content:
                raise MatrixResponseError("`start` not in response.")
            elif "end" not in content:
                raise MatrixResponseError("`start` not in response.")
            raise MatrixResponseError("`content` not in response.")
        except SerializerError as e:
            raise MatrixResponseError("Invalid events in response") from e

    # endregion
    # region 7.6 Sending events to a room
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#sending-events-to-a-room

    async def send_state_event(
        self,
        room_id: RoomID,
        event_type: EventType,
        content: StateEventContent,
        state_key: str = "",
        **kwargs,
    ) -> EventID:
        """
        Send a state event to a room. State events with the same ``room_id``, ``event_type`` and
        ``state_key`` will be overridden.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#put_matrixclientv3roomsroomidstateeventtypestatekey>`__

        Args:
            room_id: The ID of the room to set the state in.
            event_type: The type of state to send.
            content: The content to send.
            state_key: The key for the state to send. Defaults to empty string.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method. Used by
                :class:`IntentAPI` to pass the timestamp massaging field to
                :meth:`AppServiceAPI.request`.

        Returns:
            The ID of the event that was sent.
        """
        content = content.serialize() if isinstance(content, Serializable) else content
        resp = await self.api.request(
            Method.PUT,
            Path.rooms[room_id].state[event_type][state_key],
            content,
            **kwargs,
            metrics_method="sendStateEvent",
        )
        try:
            return resp["event_id"]
        except KeyError:
            raise MatrixResponseError("`event_id` not in response.")

    async def send_message_event(
        self,
        room_id: RoomID,
        event_type: EventType,
        content: EventContent,
        txn_id: str | None = None,
        **kwargs,
    ) -> EventID:
        """
        Send a message event to a room. Message events allow access to historical events and
        pagination, making them suited for "once-off" activity in a room.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#put_matrixclientv3roomsroomidsendeventtypetxnid>`__

        Args:
            room_id: The ID of the room to send the message to.
            event_type: The type of message to send.
            content: The content to send.
            txn_id: The transaction ID to use. If not provided, a random ID will be generated.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method. Used by
                :class:`IntentAPI` to pass the timestamp massaging field to
                :meth:`AppServiceAPI.request`.

        Returns:
            The ID of the event that was sent.
        """
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        url = Path.rooms[room_id].send[event_type][txn_id or self.api.get_txn_id()]
        content = content.serialize() if isinstance(content, Serializable) else content
        resp = await self.api.request(
            Method.PUT, url, content, **kwargs, metrics_method="sendMessageEvent"
        )
        try:
            return resp["event_id"]
        except KeyError:
            raise MatrixResponseError("`event_id` not in response.")

    # region Message send helper functions

    def send_message(
        self,
        room_id: RoomID,
        content: MessageEventContent,
        **kwargs,
    ) -> Awaitable[EventID]:
        """
        Send a message to a room.

        Args:
            room_id: The ID of the room to send the message to.
            content: The content to send.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method.

        Returns:
            The ID of the event that was sent.
        """
        return self.send_message_event(room_id, EventType.ROOM_MESSAGE, content, **kwargs)

    def react(self, room_id: RoomID, event_id: EventID, key: str, **kwargs) -> Awaitable[EventID]:
        content = ReactionEventContent(
            relates_to=RelatesTo(rel_type=RelationType.ANNOTATION, event_id=event_id, key=key)
        )
        return self.send_message_event(room_id, EventType.REACTION, content, **kwargs)

    async def send_text(
        self,
        room_id: RoomID,
        text: str | None = None,
        html: str | None = None,
        msgtype: MessageType = MessageType.TEXT,
        relates_to: RelatesTo | None = None,
        **kwargs,
    ) -> EventID:
        """
        Send a text message to a room.

        Args:
            room_id: The ID of the room to send the message to.
            text: The text to send. If set to ``None``, the given HTML will be parsed to generate
                  a plaintext representation.
            html: The HTML to send.
            msgtype: The message type to send.
                     Defaults to :attr:`MessageType.TEXT` (normal text message).
            relates_to: Message relation metadata used for things like replies.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method.

        Returns:
            The ID of the event that was sent.

        Raises:
            ValueError: if both ``text`` and ``html`` are ``None``.
        """
        if html is not None:
            if text is None:
                text = await parse_html(html)
            content = TextMessageEventContent(
                msgtype=msgtype, body=text, format=Format.HTML, formatted_body=html
            )
        elif text is not None:
            content = TextMessageEventContent(msgtype=msgtype, body=text)
        else:
            raise TypeError("send_text() requires either text or html to be set")
        if relates_to:
            content.relates_to = relates_to
        return await self.send_message(room_id, content, **kwargs)

    def send_notice(
        self,
        room_id: RoomID,
        text: str | None = None,
        html: str | None = None,
        relates_to: RelatesTo | None = None,
        **kwargs,
    ) -> Awaitable[EventID]:
        """
        Send a notice text message to a room. Notices are like normal text messages, but usually
        sent by bots to tell other bots not to react to them. If you're a bot, please send notices
        instead of normal text, unless there is a reason to do something else.

        Args:
            room_id: The ID of the room to send the message to.
            text: The text to send. If set to ``None``, the given HTML will be parsed to generate
                  a plaintext representation.
            html: The HTML to send.
            relates_to: Message relation metadata used for things like replies.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method.

        Returns:
            The ID of the event that was sent.

        Raises:
            ValueError: if both ``text`` and ``html`` are ``None``.
        """
        return self.send_text(room_id, text, html, MessageType.NOTICE, relates_to, **kwargs)

    def send_emote(
        self,
        room_id: RoomID,
        text: str | None = None,
        html: str | None = None,
        relates_to: RelatesTo | None = None,
        **kwargs,
    ) -> Awaitable[EventID]:
        """
        Send an emote to a room. Emotes are usually displayed by prepending a star and the user's
        display name to the message, which means they're usually written in the third person.

        Args:
            room_id: The ID of the room to send the message to.
            text: The text to send. If set to ``None``, the given HTML will be parsed to generate
                  a plaintext representation.
            html: The HTML to send.
            relates_to: Message relation metadata used for things like replies.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method.

        Returns:
            The ID of the event that was sent.

        Raises:
            ValueError: if both ``text`` and ``html`` are ``None``.
        """
        return self.send_text(room_id, text, html, MessageType.EMOTE, relates_to, **kwargs)

    def send_file(
        self,
        room_id: RoomID,
        url: ContentURI,
        info: BaseFileInfo | None = None,
        file_name: str | None = None,
        file_type: MessageType = MessageType.FILE,
        relates_to: RelatesTo | None = None,
        **kwargs,
    ) -> Awaitable[EventID]:
        """
        Send a file to a room.

        Args:
            room_id: The ID of the room to send the message to.
            url: The Matrix content repository URI of the file. You can upload files using
                :meth:`~MediaRepositoryMethods.upload_media`.
            info: Additional metadata about the file, e.g. mimetype, image size, video duration, etc
            file_name: The name for the file to send.
            file_type: The general file type to send. The file type can be further specified by
                setting the ``mimetype`` field of the ``info`` parameter. Defaults to
                :attr:`MessageType.FILE` (unspecified file type, e.g. document)
            relates_to: Message relation metadata used for things like replies.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method.

        Returns:
            The ID of the event that was sent.
        """
        return self.send_message(
            room_id,
            MediaMessageEventContent(
                url=url, info=info, body=file_name, relates_to=relates_to, msgtype=file_type
            ),
            **kwargs,
        )

    def send_sticker(
        self,
        room_id: RoomID,
        url: ContentURI,
        info: ImageInfo | None = None,
        text: str = "",
        relates_to: RelatesTo | None = None,
        **kwargs,
    ) -> Awaitable[EventID]:
        """
        Send a sticker to a room. Stickers are basically images, but they're usually rendered
        slightly differently.

        Args:
            room_id: The ID of the room to send the message to.
            url: The Matrix content repository URI of the sticker. You can upload files using
                :meth:`~MediaRepositoryMethods.upload_media`.
            info: Additional metadata about the sticker, e.g. mimetype and image size
            text: A textual description of the sticker.
            relates_to: Message relation metadata used for things like replies.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method.

        Returns:
            The ID of the event that was sent.
        """
        return self.send_message_event(
            room_id,
            EventType.STICKER,
            MediaMessageEventContent(url=url, info=info, body=text, relates_to=relates_to),
            **kwargs,
        )

    def send_image(
        self,
        room_id: RoomID,
        url: ContentURI,
        info: ImageInfo | None = None,
        file_name: str = None,
        relates_to: RelatesTo | None = None,
        **kwargs,
    ) -> Awaitable[EventID]:
        """
        Send an image to a room.

        Args:
            room_id: The ID of the room to send the message to.
            url: The Matrix content repository URI of the image. You can upload files using
                :meth:`~MediaRepositoryMethods.upload_media`.
            info: Additional metadata about the image, e.g. mimetype and image size
            file_name: The file name for the image to send.
            relates_to: Message relation metadata used for things like replies.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method.

        Returns:
            The ID of the event that was sent.
        """
        return self.send_file(
            room_id, url, info, file_name, MessageType.IMAGE, relates_to, **kwargs
        )

    # endregion

    # endregion
    # region 7.7 Redactions
    # API reference: https://spec.matrix.org/v1.1/client-server-api/#redactions

    async def redact(
        self,
        room_id: RoomID,
        event_id: EventID,
        reason: str | None = None,
        extra_content: dict[str, JSON] = {},
        **kwargs,
    ) -> EventID:
        """
        Send an event to redact a previous event.

        Redacting an event strips all information out of an event which isn't critical to the
        integrity of the server-side representation of the room.

        This cannot be undone.

        Users may redact their own events, and any user with a power level greater than or equal to
        the redact power level of the room may redact events there.

        See also: `API reference <https://spec.matrix.org/v1.1/client-server-api/#put_matrixclientv3roomsroomidredacteventidtxnid>`__

        Args:
            room_id: The ID of the room the event is in.
            event_id: The ID of the event to redact.
            reason: The reason for the event being redacted.
            extra_content: Extra content for the event.
            **kwargs: Optional parameters to pass to the :meth:`HTTPAPI.request` method. Used by
                :class:`IntentAPI` to pass the timestamp massaging field to
                :meth:`AppServiceAPI.request`.

        Returns:
            The ID of the event that was sent to redact the other event.
        """
        url = Path.rooms[room_id].redact[event_id][self.api.get_txn_id()]
        content = extra_content if not reason else {**extra_content, "reason": reason}
        resp = await self.api.request(
            Method.PUT, url, content=content, **kwargs, metrics_method="redact"
        )
        try:
            return resp["event_id"]
        except KeyError:
            raise MatrixResponseError("`event_id` not in response.")

    # endregion
