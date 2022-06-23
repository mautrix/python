# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .authentication import ClientAuthenticationMethods
from .events import EventMethods
from .filtering import FilteringMethods
from .modules import ModuleMethods
from .rooms import RoomMethods
from .user_data import UserDataMethods


class ClientAPI(
    ClientAuthenticationMethods,
    FilteringMethods,
    RoomMethods,
    EventMethods,
    UserDataMethods,
    ModuleMethods,
):
    """
    ClientAPI is a medium-level wrapper around the HTTPAPI that provides many easy-to-use
    functions for accessing the client-server API.

    This class can be used directly, but generally you should use the higher-level wrappers that
    inherit from this class, such as :class:`mautrix.client.Client`
    or :class:`mautrix.appservice.IntentAPI`.

    Examples:
        >>> from mautrix.client import ClientAPI
        >>> client = ClientAPI("@user:matrix.org", base_url="https://matrix-client.matrix-org",
                               token="syt_123_456")
        >>> await client.whoami()
        WhoamiResponse(user_id="@user:matrix.org", device_id="DEV123")
        >>> await client.get_joined_rooms()
        ["!roomid:matrix.org"]
    """
