from typing import Optional, List, Union

from ...errors import MatrixResponseError
from ...types import JSON
from .types import (UserID, RoomID, RoomAlias, StateEvent, RoomCreateVisibility, RoomCreatePreset,
                    RoomAliasInfo)
from .base import BaseClientAPI, quote


class RoomMethods(BaseClientAPI):
    """
    Methods in section 9 Rooms of the spec. See also: `API reference`_

    .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#rooms
    """

    # region 9.1 Creation
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#creation

    async def create_room(self, alias_localpart: Optional[str] = None,
                          visibility: RoomCreateVisibility = RoomCreateVisibility.PRIVATE,
                          preset: RoomCreatePreset = RoomCreatePreset.PRIVATE,
                          name: Optional[str] = None, topic: Optional[str] = None,
                          is_direct: bool = False, invitees: Optional[List[UserID]] = None,
                          initial_state: Optional[List[StateEvent]] = None,
                          room_version: str = None, creation_content: JSON = None) -> RoomID:
        """
        Create a new room with various configuration options. See also: `API reference`_

        Args:
            alias_localpart: The desired room alias **local part**. If this is included, a room
                alias will be created and mapped to the newly created room. The alias will belong on
                the same homeserver which created the room. For example, if this was set to "foo"
                and sent to the homeserver "example.com" the complete room alias would be
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
                ``m.room.member`` events sent to the users in ``invite`` and ``invite_3pid``. See
                `Direct Messaging`_ for more information.
            invitees: A list of user IDs to invite to the room. This will tell the server to invite
                everyone in the list to the newly created room.
            initial_state: A list of state events to set in the new room. This allows the user to
                override the default state events set in the new room. The expected format of the
                state events are an object with type, state_key and content keys set.

                Takes precedence over events set by ``is_public``, but gets overriden by ``name`` and
                ``topic keys``.
            room_version: The room version to set for the room. IF not provided, the homeserver will
                use its configured default.
            creation_content: Extra keys, such as ``m.federate``, to be added to the `m.room.create`
                event. The server will ignore ``creator`` and ``room_version``. Future versions of
                the specification may allow the server to ignore other keys.

        Returns:
            The ID of the newly created room.

        Raises:
            MatrixResponseError: If the response does not contain a ``room_id`` field.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-createroom
        .. _Room Events: https://matrix.org/docs/spec/client_server/r0.4.0.html#room-events
        .. _Direct Messaging: https://matrix.org/docs/spec/client_server/r0.4.0.html#direct-messaging
        .. _m.room.create: https://matrix.org/docs/spec/client_server/r0.4.0.html#m-room-create
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
            content["initial_state"] = [event.serialize() for event in initial_state]
        if room_version:
            content["room_version"] = room_version
        if creation_content:
            content["creation_content"] = creation_content

        resp = await self.api.request("POST", "/createRoom", content)
        try:
            return resp["room_id"]
        except KeyError:
            raise MatrixResponseError("`room_id` not in response.")

    # endregion
    # region 9.2 Room aliases
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#room-aliases

    async def add_room_alias(self, room_alias: RoomAlias, room_id: RoomID) -> None:
        """
        Create a new mapping from room alias to room ID. See also: `API reference`_

        Args:
            room_alias: The room alias to set.
            room_id: The room ID to set.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-directory-room-roomalias
        """
        await self.api.request("PUT", f"/directory/room/{quote(room_alias)}", {
            "room_id": room_id,
        })

    async def remove_room_alias(self, room_alias: RoomAlias) -> None:
        """
        Remove a mapping of room alias to room ID.

        Servers may choose to implement additional access control checks here, for instance that
        room aliases can only be deleted by their creator or server administrator. See also: `API
        reference`_

        Args:
            room_alias: The room alias to remove.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#delete-matrix-client-r0-directory-room-roomalias
        """
        await self.api.request("DELETE", f"/directory/room/{quote(room_alias)}")

    async def get_room_alias(self, room_alias: RoomAlias) -> RoomAliasInfo:
        """
        Request the server to resolve a room alias to a room ID.

        The server will use the federation API to resolve the alias if the domain part of the alias
        does not correspond to the server's own domain.

        See also: `API reference`_

        Args:
            room_alias: The room alias.

        Returns:
            The room ID and a list of servers that are aware of the room.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-directory-room-roomalias
        """
        content = await self.api.request("GET", f"/directory/room/{quote(room_alias)}")
        return RoomAliasInfo.deserialize(content)

    # endregion
    # region 9.4 Room membership
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#room-membership

    async def get_joined_rooms(self) -> List[RoomID]:
        """Get the list of rooms the user is in."""
        content = await self.api.request("GET", "/joined_rooms")
        try:
            return content["joined_rooms"]
        except KeyError:
            raise MatrixResponseError("`joined_rooms` not in response.")

    # region 9.4.2 Joining rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#joining-rooms

    async def join_room_by_id(self, room_id: RoomID, third_party_signed: JSON = None) -> RoomID:
        """
        Join a room by its ID. See also: `API reference`_

        Args:
            room_id: The ID of the room to join.
            third_party_signed: A signature of an ``m.third_party_invite`` token to prove that this
                user owns a third party identity which has been invited to the room.

        Returns:
            The ID of the room the user joined.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-rooms-roomid-join
        """
        content = await self.api.request("POST", f"/rooms/{quote(room_id)}/join", {
            "third_party_signed": third_party_signed,
        } if third_party_signed is not None else None)
        try:
            return content["room_id"]
        except KeyError:
            raise MatrixResponseError("`room_id` not in response.")

    async def join_room(self, room_id_or_alias: Union[RoomID, RoomAlias], servers: List[str] = None,
                        third_party_signed: JSON = None) -> RoomID:
        """
        Join a room by its ID or alias, with an optional list of servers to ask about the ID from.
        See also: `API reference`_

        Args:
            room_id_or_alias: The ID of the room to join, or an alias pointing to the room.
            servers: A list of servers to ask about the room ID to join. Not applicable for aliases,
                as aliases already contain the necessary server information.
            third_party_signed: A signature of an ``m.third_party_invite`` token to prove that this
                user owns a third party identity which has been invited to the room.

        Returns:
            The ID of the room the user joined.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-join-roomidoralias
        """
        content = await self.api.request("POST", f"/join/{quote(room_id_or_alias)}",
                                         content={
                                             "third_party_signed": third_party_signed,
                                         } if third_party_signed is not None else None,
                                         query_params={
                                             "servers": servers,
                                         } if servers is not None else None)
        try:
            return content["room_id"]
        except KeyError:
            raise MatrixResponseError("`room_id` not in response.")

    async def invite_user(self):
        pass

    # endregion
    # region 9.4.3 Leaving rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#leaving-rooms

    async def leave_room(self):
        pass

    async def forget_room(self):
        pass

    async def kick_user(self):
        pass

    # endregion
    # region 9.4.4 Banning users in a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#banning-users-in-a-room

    async def ban_user(self):
        pass

    async def unban_user(self):
        pass

    # endregion

    # endregion
    # region 9.5 Listing rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#listing-rooms

    def get_room_directory_visibility(self):
        pass

    def set_room_directory_visibility(self):
        pass

    def get_room_directory(self):
        pass

    def get_filtered_room_directory(self):
        pass

    # endregion
