# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional

from mautrix.errors import MatrixResponseError
from mautrix.api import Method, Path
from mautrix.types import RoomID, UserID, EventID, PresenceEventContent, PresenceState, SerializerError

from ..base import BaseClientAPI


class MiscModuleMethods(BaseClientAPI):
    """
    Miscellaneous subsections in the `Modules section`_ of the API spec.

    Currently included subsections:

    * 13.4 `Typing Notifications`_
    * 13.5 `Receipts`_
    * 13.6 `Fully Read Markers`_
    * 13.7 `Presence`_

    .. _Modules section: https://matrix.org/docs/spec/client_server/r0.4.0.html#modules
    .. _Typing Notifications: https://matrix.org/docs/spec/client_server/r0.4.0.html#id95
    .. _Receipts: https://matrix.org/docs/spec/client_server/r0.4.0.html#id99
    .. _Fully Read Markers: https://matrix.org/docs/spec/client_server/r0.4.0.html#fully-read-markers
    .. _Presence: https://matrix.org/docs/spec/client_server/r0.4.0.html#id107
    """

    # region 13.4 Typing Notifications

    async def set_typing(self, room_id: RoomID, timeout: int = 0) -> None:
        """
        This tells the server that the user is typing for the next N milliseconds where N is the
        value specified in the timeout key. If the timeout is equal to or less than zero, it tells
        the server that the user has stopped typing.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-rooms-roomid-typing-userid>`__

        Args:
            room_id: The ID of the room in which the user is typing.
            timeout: The length of time in seconds to mark this user as typing.
        """
        if timeout > 0:
            content = {"typing": True, "timeout": timeout}
        else:
            content = {"typing": False}
        await self.api.request(Method.PUT, Path.rooms[room_id].typing[self.mxid], content)

    # endregion
    # region 13.5 Receipts

    async def send_receipt(self, room_id: RoomID, event_id: EventID, receipt_type: str = "m.read",
                           ) -> None:
        """
        Update the marker for the given receipt type to the event ID specified.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-rooms-roomid-receipt-receipttype-eventid>`__

        Args:
            room_id: The ID of the room which to send the receipt to.
            event_id: The last event ID to acknowledge.
            receipt_type: The type of receipt to send. Currently only ``m.read`` is supported.
        """
        await self.api.request(Method.POST, Path.rooms[room_id].receipt[receipt_type][event_id])

    # endregion
    # region 13.6 Fully read markers

    async def set_fully_read_marker(self, room_id: RoomID, fully_read: EventID,
                                    read_receipt: Optional[EventID] = None) -> None:
        """
        Set the position of the read marker for the given room, and optionally send a new read
        receipt.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-rooms-roomid-read-markers>`__

        Args:
            room_id: The ID of the room which to set the read marker in.
            fully_read: The last event up to which the user has either read all events or is not
                interested in reading the events.
            read_receipt: The new position for the user's normal read receipt, i.e. the last event
                the user has seen.
        """
        content = {
            "m.fully_read": fully_read,
        }
        if read_receipt:
            content["m.read"] = read_receipt
        await self.api.request(Method.POST, Path.rooms[room_id].read_markers, content)

    # endregion
    # region 13.7 Presence

    async def set_presence(self, presence: PresenceState = PresenceState.ONLINE,
                           status: Optional[str] = None) -> None:
        """
        Set the current user's presence state. When setting the status, the activity time is updated
        to reflect that activity; the client does not need to specify
        :attr:`Presence.last_active_ago`.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-presence-list-userid>`__

        Args:
            presence: The new presence state to set.
            status: The status message to attach to this state.
        """
        content = {
            "presence": presence.value,
        }
        if status:
            content["status_msg"] = status
        await self.api.request(Method.PUT, Path.presence[self.mxid].status, content)

    async def get_presence(self, user_id: UserID) -> PresenceEventContent:
        """
        Get the presence info of a user.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-presence-list-userid>`__

        Args:
            user_id: The ID of the user whose presence info to get.

        Returns:
            The presence info of the given user.
        """
        content = await self.api.request(Method.GET, Path.presence[user_id].status)
        try:
            return PresenceEventContent.deserialize(content)
        except SerializerError:
            raise MatrixResponseError("Invalid presence in response")

    # endregion
