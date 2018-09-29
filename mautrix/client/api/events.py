from time import time
from typing import Awaitable, Dict, Optional, List, Tuple

from ...api import MatrixResponseError
from .types import UserID, RoomID, EventID, Event, EventType, EventContent, Member
from .base import BaseClientAPI, quote


class EventMethods(BaseClientAPI):
    """
    Methods in section 8 Events of the spec. See also: `API reference`_

    .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#events
    """

    # region 8.2 Syncing
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#syncing

    def sync(self, since: str = None, timeout_ms: int = 30000, filter_id: int = None,
             full_state: bool = None, set_presence: str = None) -> Awaitable[Dict]:
        """
        Perform a sync request. See also: `API reference`_

        Args:
            since (str): Optional. A token which specifies where to continue a sync from.
            timeout_ms (int): Optional. The time in milliseconds to wait.
            filter_id (int): A filter ID.
            full_state (bool): Return the full state for every room the user has joined
                Defaults to false.
            set_presence (str): Should the client be marked as "online" or" offline"

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-sync
        """
        request = {"timeout": timeout_ms}
        if since:
            request["since"] = since
        if filter_id:
            request["filter"] = filter_id
        if full_state:
            request["full_state"] = "true"
        if set_presence:
            request["set_presence"] = set_presence
        return self.api.request("GET", "/sync", query_params=request)

    # endregion
    # region 8.3 Getting events for a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#getting-events-for-a-room

    async def get_event(self, room_id: RoomID, event_id: EventID) -> Event:
        """
        Get a single event based on ``room_id``/``event_id``. You must have permission to retrieve this
        event e.g. by being a member in the room for this event. See also: `API reference`_

        Args:
            room_id: The ID of the room the event is in.
            event_id: The event ID to get.

        Returns:
            The event.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#id247
        """
        content = await self.api.request("GET", f"/rooms/{quote(room_id)}/event/{quote(event_id)}")
        return Event.deserialize(content)

    async def get_state_event(self, room_id: RoomID, event_type: EventType,
                              state_key: Optional[str] = None) -> Event:
        """
        Looks up the contents of a state event in a room. If the user is joined to the room then the
        state is taken from the current state of the room. If the user has left the room then the
        state is taken from the state of the room when they left. See also: `API reference`_

        Args:
            room_id: The ID of the room to look up the state in.
            event_type: The type of state to look up.
            state_key: The key of the state to look up. Defaults to empty string.

        Returns:
            The state event.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-rooms-roomid-state-eventtype-statekey
        """
        content = await self.api.request("GET", self._get_state_url(room_id, event_type, state_key))
        return Event.deserialize(content)

    async def get_state(self, room_id: RoomID) -> List[Event]:
        """
        Get the state events for the current state of a room. See also: `API reference`_

        Args:
            room_id: The ID of the room to look up the state for.

        Returns:
            A list of state events with the most recent of each event_type/state_key pair.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-rooms-roomid-state
        """
        content = await self.api.request("GET", f"/rooms/{quote(room_id)}/state")
        return [Event.deserialize(event) for event in content]

    async def get_members(self, room_id: RoomID) -> List[Event]:
        """
        Get the list of members for a room. See also: `API reference`_

        Args:
            room_id: The ID of the room to get the member events for.

        Returns:
            A list of most recent member events for each user.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-rooms-roomid-members
        """
        content = await self.api.request("GET", f"/rooms/{quote(room_id)}/members")
        try:
            chunk = content["chunk"]
        except KeyError:
            raise MatrixResponseError("`chunk` not in response.")
        return [Event.deserialize(event) for event in chunk]

    async def get_joined_members(self, room_id: RoomID) -> Dict[UserID, Member]:
        """
        Get a user ID -> member info map for a room. The current user must be in the room for it to
        work, unless it is an Application Service in which case any of the AS's users must be in the
        room. This API is primarily for Application Services and should be faster to respond than
        `/members`_ as it can be implemented more efficiently on the server. See also: `API reference`_

        Args:
            room_id: The ID of the room to get the members of.

        Returns:
            A dictionary from user IDs to Member info objects.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-rooms-roomid-joined-members
        .. _/members: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-rooms-roomid-members
        """
        content = await self.api.request("GET", f"/rooms/{quote(room_id)}/members")
        try:
            joined = content["joined"]
        except KeyError:
            raise MatrixResponseError("`joined` not in response.")
        return {user_id: Member.deserialize(event) for user_id, event in joined}

    async def get_messages(self, room_id: RoomID, direction: str, from_token: str,
                           to_token: Optional[str] = None, limit: Optional[int] = None,
                           filter_json: Optional[str] = None) -> Tuple[str, str, List[Event]]:
        """
        Get a list of message and state events for a room. Pagination parameters are used to
        paginate history in the room. See also: `API reference`_

        Args:
            room_id: The ID of the room to get events from.
            direction: The direction to return events from. One of: ["b", "f"]
            from_token: The token to start returning events from. This token can be obtained from a
                ``prev_batch`` token returned for each room by the `sync endpoint`_, or from a
                ``start`` or ``end`` token returned by a previous request to this endpoint.
            to_token: The token to stop returning events at.
            limit: The maximum number of events to return. Defaults to 10.
            filter_json: A JSON RoomEventFilter_ to filter returned events with.

        Returns:

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-rooms-roomid-messages
        .. _RoomEventFilter: https://matrix.org/docs/spec/client_server/r0.4.0.html#filtering
        .. _sync endpoint: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-sync
        """
        if len(direction) == 0 or direction[0] not in ("b", "f"):
            raise ValueError("Invalid direction. Valid values: b, f")
        query_params = {
            "from": from_token,
            "dir": direction[0],
        }
        if to_token:
            query_params["to"] = to_token
        if limit:
            query_params["limit"] = str(limit)
        if filter:
            query_params["filter"] = filter_json
        content = await self.api.request("GET", f"/rooms/{quote(room_id)}/messages",
                                         query_params=query_params)
        try:
            return (content["start"], content["end"],
                    [Event.deserialize(event) for event in content["chunk"]])
        except KeyError:
            if "start" not in content:
                raise MatrixResponseError("`start` not in response.")
            elif "end" not in content:
                raise MatrixResponseError("`start` not in response.")
            raise MatrixResponseError("`content` not in response.")

    # endregion
    # region 8.4 Sending events to a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#sending-events-to-a-room

    def _get_state_url(self, room_id: RoomID, event_type: EventType, state_key: Optional[str] = ""
                       ) -> str:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        url = f"/rooms/{quote(room_id)}/state/{quote(str(event_type))}"
        if state_key:
            url += f"/{quote(state_key)}"
        return url

    async def send_state_event(self, room_id: RoomID, event_type: EventType, content: EventContent,
                               state_key: Optional[str] = "", **kwargs) -> EventID:
        """
        Send a state event to a room. State events with the same ``room_id``, ``event_type`` and
        ``state_key`` will be overridden. See also: `API reference`_

        Args:
            room_id: The ID of the room to set the state in.
            event_type: The type of state to send.
            content: The content to send.
            state_key: The key for the state to send. Defaults to empty string.
            **kwargs: Optional parameters to pass to the :HTTPAPI:`request` method. Used by the
                :IntentAPI: to pass timestamp massaging and external URL fields to
                :AppServiceAPI:`request`.

        Returns:
            The ID of the event that was sent.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-rooms-roomid-state-eventtype-statekey
        """
        url = self._get_state_url(room_id, event_type, state_key)
        resp = await self.api.request("PUT", url, content.serialize(), **kwargs)
        try:
            return resp["event_id"]
        except KeyError:
            raise MatrixResponseError("`event_id` not in response.")

    async def send_message_event(self, room_id: RoomID, event_type: EventType,
                                 content: EventContent, **kwargs) -> EventID:
        """
        Send a message event to a room. Message events allow access to historical events and
        pagination, making them suited for "once-off" activity in a room. See also: `API reference`_

        Args:
            room_id: The ID of the room to send the message to.
            event_type: The type of message to send.
            content: The content to send.
            **kwargs: Optional parameters to pass to the :HTTPAPI:`request` method. Used by the
                :IntentAPI: to pass timestamp massaging and external URL fields to
                :AppServiceAPI:`request`.

        Returns:
            The ID of the event that was sent.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-rooms-roomid-send-eventtype-txnid
        """
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        url = f"/rooms/{quote(room_id)}/send/{quote(str(event_type))}/{self.api.get_txn_id()}"
        resp = await self.api.request("PUT", url, content.serialize(), **kwargs)
        try:
            return resp["event_id"]
        except KeyError:
            raise MatrixResponseError("`event_id` not in response.")

    # endregion
    # region 8.5 Redactions
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#redactions

    async def redact(self, room_id: RoomID, event_id: EventID,
                     reason: Optional[str] = "") -> EventID:
        """
        Send an event to redact a previous event.

        Redacting an event strips all information out of an event which isn't critical to the
        integrity of the server-side representation of the room.

        This cannot be undone.

        Users may redact their own events, and any user with a power level greater than or equal to
        the redact power level of the room may redact events there.

        See also: `API reference`_

        Args:
            room_id: The ID of the room the event is in.
            event_id: The ID of the event to redact.
            reason: The reason for the event being redacted.

        Returns:
            The ID of the event that was sent to redact the other event.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-rooms-roomid-redact-eventid-txnid
        """
        url = f"/rooms/{quote(room_id)}/redact/{quote(event_id)}/{self.api.get_txn_id()}"
        resp = await self.api.request("PUT", url)
        try:
            return resp["event_id"]
        except KeyError:
            raise MatrixResponseError("`event_id` not in response.")

    # endregion
