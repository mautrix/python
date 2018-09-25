# -*- coding: future_fstrings -*-
from typing import Awaitable, Dict
import re

from .http import HTTPAPI


class ClientAPI:
    """
    ClientAPI is a medium-level wrapper around the HTTPAPI that provides many easy-to-use
    functions for accessing the client-server API.
    """

    mxid_regex = re.compile("@(.+):(.+)")

    def __init__(self, mxid: str, client: 'HTTPAPI'):
        mxid_parts = self.mxid_regex.match(mxid)
        if not mxid_parts:
            raise ValueError("invalid MXID")
        self.localpart = mxid_parts.group(1)
        self.domain = mxid_parts.group(2)

        self.mxid = mxid
        self.client = client

    # region 7 Filtering
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#filtering

    def get_filter(self, user_id: str, filter_id: str) -> Awaitable[Dict]:
        """
        Download a filter. See also: `API reference`_

        Args:
            user_id: The user ID to download a filter for.
            filter_id: The filter ID to download.

        Returns:
            The filter data.

        .. _API reference:
            https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-user-userid-filter-filterid
        """
        return self.client.request("GET", f"/user/{user_id}/filter/{filter_id}")

    async def create_filter(self, user_id: str, filter_params: Dict) -> str:
        """
        Upload a new filter definition to the homeserver. See also: `API reference`_

        Args:
            user_id: The ID of the user uploading the filter.
            filter_params: The filter data.

        Returns:
            A filter ID that can be used in future requests to refer to the uploaded filter.

        .. _API reference:
            https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-user-userid-filter
        """
        resp = await self.client.request("POST", f"/user/{user_id}/filter", filter_params)
        return resp.get("filter_id", None)

    # endregion
    # region 8 Events
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#events

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

        .. _API reference:
            https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-sync
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
        return self.client.request("GET", "/sync", query_params=request)

    # endregion
    # region 8.3 Getting events for a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#getting-events-for-a-room

    # TODO

    # endregion
    # region 8.4 Sending events to a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#sending-events-to-a-room

    # TODO

    # endregion
    # region 8.5 Redactions
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#redactions

    # TODO

    # endregion

    # endregion
    # region 9 Rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#rooms

    # region 9.1 Creation
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#creation

    async def create_room(self):
        raise NotImplementedError()

    # endregion
    # region 9.2 Room aliases https://matrix.org/docs/spec/client_server/r0.4.0.html#room-aliases

    async def add_room_alias(self):
        raise NotImplementedError()

    async def remove_room_alias(self):
        raise NotImplementedError()

    async def get_room_alias(self):
        raise NotImplementedError()

    # endregion
    # region 9.4 Room membership
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#room-membership

    async def get_joined_rooms(self):
        raise NotImplementedError()

    # region 9.4.2 Joining rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#joining-rooms

    async def join_room_by_id(self):
        raise NotImplementedError()

    async def join_room(self):
        raise NotImplementedError()

    async def invite_user(self):
        raise NotImplementedError()

    # endregion
    # region 9.4.3 Leaving rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#leaving-rooms

    async def leave_room(self):
        raise NotImplementedError()

    async def forget_room(self):
        raise NotImplementedError()

    async def kick_user(self):
        raise NotImplementedError()

    # endregion
    # region 9.4.4 Banning users in a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#banning-users-in-a-room

    async def ban_user(self):
        raise NotImplementedError()

    async def unban_user(self):
        raise NotImplementedError

    # endregion

    # endregion
    # region 9.5 Listing rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#listing-rooms

    def get_room_directory_visibility(self):
        raise NotImplementedError()

    def set_room_directory_visibility(self):
        raise NotImplementedError()

    def get_room_directory(self):
        raise NotImplementedError()

    def get_filtered_room_directory(self):
        raise NotImplementedError()

    # endregion

    # endregion
    # region 10 User Data
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#user-data

    # region 10.1 User Directory
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#user-directory

    async def search_users(self):
        raise NotImplementedError()

    # endregion
    # region 10.2 Profiles
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#profiles

    async def set_displayname(self):
        raise NotImplementedError()

    async def get_displayname(self):
        raise NotImplementedError()

    async def set_avatar_url(self):
        raise NotImplementedError()

    async def get_avatar_url(self):
        raise NotImplementedError()

    async def get_profile(self):
        raise NotImplementedError()

    # endregion

    # endregion
    # region 13 Modules
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#modules

    # region 13.4 Typing Notifications
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#id95

    async def set_typing(self):
        raise NotImplementedError()

    # endregion
    # region 13.5 Receipts
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#id99

    async def send_receipt(self):
        raise NotImplementedError()

    async def mark_read(self):
        raise NotImplementedError()

    # endregion
    # region 13.6 Fully read markers
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#fully-read-markers

    async def mark_fully_read(self):
        raise NotImplementedError()

    # endregion
    # region 13.7 Presence
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#id107

    async def set_presence(self):
        raise NotImplementedError()

    async def get_presence(self):
        raise NotImplementedError()

    # endregion
    # region 13.8 Content Repository
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#id112

    async def upload_media(self):
        raise NotImplementedError()

    async def download_media(self):
        raise NotImplementedError()

    async def download_thumbnail(self):
        raise NotImplementedError()

    async def get_url_preview(self):
        raise NotImplementedError()

    async def get_media_repo_config(self):
        raise NotImplementedError()

    # endregion

    # TODO: subregions 15, 18, 19, 21, 26, 27, others?

    # endregion
