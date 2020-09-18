# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Optional, Union

from mautrix.errors import MatrixResponseError
from mautrix.api import Method, Path
from mautrix.types import (UserID, LoginType, UserIdentifier, LoginResponse, LoginFlowList,
                           MatrixUserIdentifier)

from .base import BaseClientAPI


class ClientAuthenticationMethods(BaseClientAPI):
    """
    Methods in section 5 Authentication of the spec. These methods are used for setting and getting user
    metadata and searching for users.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1.html#client-authentication>`__
    """

    # region 5.5 Login
    # API reference: https://matrix.org/docs/spec/client_server/r0.6.1.html#login

    async def get_login_flows(self) -> LoginFlowList:
        """
        Get login flows supported by the homeserver.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#get-matrix-client-r0-login>`__

        Returns:
            The list of login flows that the homeserver supports.
        """
        resp = await self.api.request(Method.GET, Path.login)
        try:
            return LoginFlowList.deserialize(resp)
        except KeyError:
            raise MatrixResponseError("`flows` not in response.")

    async def login(self, identifier: Optional[Union[UserIdentifier, UserID]] = None,
                    login_type: LoginType = LoginType.PASSWORD, device_name: Optional[str] = None,
                    device_id: Optional[str] = None, password: Optional[str] = None,
                    store_access_token: bool = True, update_hs_url: bool = False, **kwargs: str
                    ) -> LoginResponse:
        """
        Authenticates the user, and issues an access token they can use to authorize themself in
        subsequent requests.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-login>`__

        Args:
            login_type: The login type being used.
            identifier: Identification information for the user.
            device_name: A display name to assign to the newly-created device.
                Ignored if ``device_id`` correspnods to a known device.
            device_id: ID of the client device. If this does not correspond to a known client
                device, a new device will be created. The server will auto-generate a device_id
                if this is not specified.
            password: The user's password. Required when `type` is `m.login.password`.
            store_access_token: Whether or not mautrix-python should store the returned access token
                in this ClientAPI instance for future requests.
            update_hs_url: Whether or not mautrix-python should use the returned homeserver URL
                in this ClientAPI instance for future requests.
            **kwargs: Additional arguments for other login types.

        Returns:
            The login response.
        """
        if identifier is None or isinstance(identifier, str):
            identifier = MatrixUserIdentifier(identifier or self.mxid)
        if password is not None:
            kwargs["password"] = password
        if device_name is not None:
            kwargs["initial_device_display_name"] = device_name
        if device_id:
            kwargs["device_id"] = device_id
        elif self.device_id:
            kwargs["device_id"] = self.device_id
        resp = await self.api.request(Method.POST, Path.login, {
            "type": str(login_type),
            "identifier": identifier.serialize(),
            **kwargs,
        })
        resp_data = LoginResponse.deserialize(resp)
        if store_access_token:
            self.mxid = resp_data.user_id
            self.device_id = resp_data.device_id
            self.api.token = resp_data.access_token
        if update_hs_url:
            base_url = resp_data.well_known.homeserver.base_url
            if base_url and base_url != self.api.base_url:
                self.log.debug("Login response contained new base URL, switching from "
                               f"{self.api.base_url} to {base_url}")
                self.api.base_url = base_url.rstrip("/")
        return resp_data

    async def logout(self, clear_access_token: bool = True) -> None:
        """
        Invalidates an existing access token, so that it can no longer be used for authorization.
        The device associated with the access token is also deleted.
        `Device keys <https://matrix.org/docs/spec/client_server/latest#device-keys>`__ for the
        device are deleted alongside the device.

        See also: `API reference <https://matrix.org/docs/spec/client_server/latest#post-matrix-client-r0-logout>`__

        Args:
            clear_access_token: Whether or not mautrix-python should forget the stored access token.
        """
        await self.api.request(Method.POST, Path.logout)
        if clear_access_token:
            self.api.token = ""
            self.device_id = ""

    async def logout_all(self, clear_access_token: bool = True) -> None:
        """
        Invalidates all access tokens for a user, so that they can no longer be used for
        authorization. This includes the access token that made this request. All devices for the
        user are also deleted.
        `Device keys <https://matrix.org/docs/spec/client_server/latest#device-keys>`__ for the
        device are deleted alongside the device.

        This endpoint does not require UI (user-interactive) authorization because UI authorization
        is designed to protect against attacks where the someone gets hold of a single access token
        then takes over the account. This endpoint invalidates all access tokens for the user,
        including the token used in the request, and therefore the attacker is unable to take over
        the account in this way.

        See also: `API reference <https://matrix.org/docs/spec/client_server/latest#post-matrix-client-r0-logout-all>`__

        Args:
            clear_access_token: Whether or not mautrix-python should forget the stored access token.
        """
        await self.api.request(Method.POST, Path.logout.all)
        if clear_access_token:
            self.api.token = ""
            self.device_id = ""

    # endregion

    # TODO other sections

    # region 5.7 Current account information
    # API reference: https://matrix.org/docs/spec/client_server/r0.6.1.html#current-account-information

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
