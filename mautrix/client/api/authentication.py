# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from ...errors import MatrixResponseError
from ...api import Method, Path
from .types import UserID
from .base import BaseClientAPI


class ClientAuthenticationMethods(BaseClientAPI):
    """
    Methods in section 5 Authentication of the spec. These methods are used for setting and getting user
    metadata and searching for users.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#client-authentication>`__
    """

    # TODO other sections

    # region 5.7 Current account information
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#current-account-information

    async def whoami(self) -> UserID:
        """
        Get information about the current user.

        Returns:
            The user ID of the current user.
        """
        resp = await self.api.request(Method.GET, Path.account.whoami)
        try:
            return resp["user_id"]
        except KeyError:
            raise MatrixResponseError("`user_id` not in response.")

    # endregion
