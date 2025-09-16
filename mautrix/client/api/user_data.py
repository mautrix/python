# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any

from mautrix.api import Method, Path
from mautrix.errors import MatrixResponseError, MNotFound
from mautrix.types import ContentURI, Member, SerializerError, User, UserID, UserSearchResults

from .base import BaseClientAPI


class UserDataMethods(BaseClientAPI):
    """
    Methods in section 10 User Data of the spec. These methods are used for setting and getting user
    metadata and searching for users.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#user-data>`__
    """

    # region 10.1 User Directory
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#user-directory

    async def search_users(self, search_query: str, limit: int | None = 10) -> UserSearchResults:
        """
        Performs a search for users on the homeserver. The homeserver may determine which subset of
        users are searched, however the homeserver MUST at a minimum consider the users the
        requesting user shares a room with and those who reside in public rooms (known to the
        homeserver). The search MUST consider local users to the homeserver, and SHOULD query remote
        users as part of the search.

        The search is performed case-insensitively on user IDs and display names preferably using a
        collation determined based upon the Accept-Language header provided in the request, if
        present.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-user-directory-search>`__

        Args:
            search_query: The query to search for.
            limit: The maximum number of results to return.

        Returns:
            The results of the search and whether or not the results were limited.
        """
        content = await self.api.request(
            Method.POST,
            Path.v3.user_directory.search,
            {
                "search_term": search_query,
                "limit": limit,
            },
        )
        try:
            return UserSearchResults(
                [User.deserialize(user) for user in content["results"]], content["limited"]
            )
        except SerializerError as e:
            raise MatrixResponseError("Invalid user in search results") from e
        except KeyError:
            if "results" not in content:
                raise MatrixResponseError("`results` not in content.")
            elif "limited" not in content:
                raise MatrixResponseError("`limited` not in content.")
            raise

    # endregion
    # region 10.2 Profiles
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#profiles

    async def set_displayname(self, displayname: str | None, check_current: bool = True) -> None:
        """
        Set the display name of the current user.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-profile-userid-displayname>`__

        Args:
            displayname: The new display name for the user.
            check_current: Whether or not to check if the displayname is already set.
        """
        if check_current and str_or_none(await self.get_displayname(self.mxid)) == str_or_none(
            displayname
        ):
            return
        await self.api.request(
            Method.PUT,
            Path.v3.profile[self.mxid].displayname,
            {
                "displayname": displayname,
            },
        )

    async def get_displayname(self, user_id: UserID) -> str | None:
        """
        Get the display name of a user.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-profile-userid-displayname>`__

        Args:
            user_id: The ID of the user whose display name to get.

        Returns:
            The display name of the given user.
        """
        try:
            content = await self.api.request(Method.GET, Path.v3.profile[user_id].displayname)
        except MNotFound:
            return None
        try:
            return content["displayname"]
        except KeyError:
            return None

    async def set_avatar_url(
        self, avatar_url: ContentURI | None, check_current: bool = True
    ) -> None:
        """
        Set the avatar of the current user.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#put-matrix-client-r0-profile-userid-avatar-url>`__

        Args:
            avatar_url: The ``mxc://`` URI to the new avatar.
            check_current: Whether or not to check if the avatar is already set.
        """
        if check_current and str_or_none(await self.get_avatar_url(self.mxid)) == str_or_none(
            avatar_url
        ):
            return
        await self.api.request(
            Method.PUT,
            Path.v3.profile[self.mxid].avatar_url,
            {
                "avatar_url": avatar_url,
            },
        )

    async def get_avatar_url(self, user_id: UserID) -> ContentURI | None:
        """
        Get the avatar URL of a user.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-profile-userid-avatar-url>`__

        Args:
            user_id: The ID of the user whose avatar to get.

        Returns:
            The ``mxc://`` URI to the user's avatar.
        """
        try:
            content = await self.api.request(Method.GET, Path.v3.profile[user_id].avatar_url)
        except MNotFound:
            return None
        try:
            return content["avatar_url"]
        except KeyError:
            return None

    async def get_profile(self, user_id: UserID) -> Member:
        """
        Get the combined profile information for a user.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-profile-userid>`__

        Args:
            user_id: The ID of the user whose profile to get.

        Returns:
            The profile information of the given user.
        """
        content = await self.api.request(Method.GET, Path.v3.profile[user_id])
        try:
            return Member.deserialize(content)
        except SerializerError as e:
            raise MatrixResponseError("Invalid member in response") from e

    # endregion

    # region Beeper Custom Fields API

    async def beeper_update_profile(self, custom_fields: dict[str, Any]) -> None:
        """
        Set custom fields on the user's profile. Only works on Hungryserv.

        Args:
            custom_fields: A dictionary of fields to set in the custom content of the profile.
        """
        await self.api.request(Method.PATCH, Path.v3.profile[self.mxid], custom_fields)

    # endregion


def str_or_none(v: str | None) -> str | None:
    """
    str_or_none empty string values to None
    """
    return None if v == "" else v
