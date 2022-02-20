# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.api import Method, Path
from mautrix.types import RoomID, RoomTagAccountDataEventContent, RoomTagInfo, Serializable

from ..base import BaseClientAPI


class RoomTaggingMethods(BaseClientAPI):
    """
    Methods in section 13.18 Room Tagging of the spec. These methods are used for organizing rooms
    into tags for the local user.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#room-tagging>`__"""

    async def get_room_tags(self, room_id: RoomID) -> RoomTagAccountDataEventContent:
        """
        Get all tags for a specific room. This is equivalent to getting the ``m.tag`` account data
        event for the room.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#get-matrix-client-r0-user-userid-rooms-roomid-tags>`__

        Args:
            room_id: The room ID to get tags from.

        Returns:
            The m.tag account data event.
        """
        resp = await self.api.request(Method.GET, Path.v3.user[self.mxid].rooms[room_id].tags)
        return RoomTagAccountDataEventContent.deserialize(resp)

    async def get_room_tag(self, room_id: RoomID, tag: str) -> RoomTagInfo | None:
        """
        Get the info of a specific tag for a room.

        Args:
            room_id: The room to get the tag from.
            tag: The tag to get.

        Returns:
            The info about the tag, or ``None`` if the room does not have the specified tag.
        """
        resp = await self.get_room_tags(room_id)
        try:
            return resp.tags[tag]
        except KeyError:
            return None

    async def set_room_tag(
        self, room_id: RoomID, tag: str, info: RoomTagInfo | None = None
    ) -> None:
        """
        Add or update a tag for a specific room.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#put-matrix-client-r0-user-userid-rooms-roomid-tags-tag>`__

        Args:
            room_id: The room ID to add the tag to.
            tag: The tag to add.
            info: Optionally, information like ordering within the tag.
        """
        await self.api.request(
            Method.PUT,
            Path.v3.user[self.mxid].rooms[room_id].tags[tag],
            content=(info.serialize() if isinstance(info, Serializable) else (info or {})),
        )

    async def remove_room_tag(self, room_id: RoomID, tag: str) -> None:
        """
        Remove a tag from a specific room.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#delete-matrix-client-r0-user-userid-rooms-roomid-tags-tag>`__

        Args:
            room_id: The room ID to remove the tag from.
            tag: The tag to remove.
        """
        await self.api.request(Method.DELETE, Path.v3.user[self.mxid].rooms[room_id].tags[tag])
