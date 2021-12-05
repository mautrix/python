# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.api import Method, Path
from mautrix.types import JSON, AccountDataEventContent, EventType, RoomID, Serializable

from ..base import BaseClientAPI


class AccountDataMethods(BaseClientAPI):
    """
    Methods in section 13.9 Client Config of the spec. These methods are used for storing user-local
    data on the homeserver to synchronize client configuration across sessions.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#id125>`__"""

    async def get_account_data(self, type: EventType | str, room_id: RoomID | None = None) -> JSON:
        """
        Get a specific account data event from the homeserver.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#get-matrix-client-r0-user-userid-account-data-type>`__

        Args:
            type: The type of the account data event to get.
            room_id: Optionally, the room ID to get per-room account data.

        Returns:
            The data in the event.
        """
        if isinstance(type, EventType) and not type.is_account_data:
            raise ValueError("Event type is not an account data event type")
        base_path = Path.user[self.mxid]
        if room_id:
            base_path = base_path.rooms[room_id]
        return await self.api.request(Method.GET, base_path.account_data[type])

    async def set_account_data(
        self,
        type: EventType | str,
        data: AccountDataEventContent | dict[str, JSON],
        room_id: RoomID | None = None,
    ) -> None:
        """
        Store account data on the homeserver.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#put-matrix-client-r0-user-userid-account-data-type>`__

        Args:
            type: The type of the account data event to set.
            data: The content to store in that account data event.
            room_id: Optionally, the room ID to set per-room account data.
        """
        if isinstance(type, EventType) and not type.is_account_data:
            raise ValueError("Event type is not an account data event type")
        base_path = Path.user[self.mxid]
        if room_id:
            base_path = base_path.rooms[room_id]
        await self.api.request(
            Method.PUT,
            base_path.account_data[type],
            data.serialize() if isinstance(data, Serializable) else data,
        )
