# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .authentication import ClientAuthenticationMethods
from .filtering import FilteringMethods
from .events import EventMethods
from .rooms import RoomMethods
from .user_data import UserDataMethods
from .modules import ModuleMethods


class ClientAPI(ClientAuthenticationMethods, FilteringMethods, EventMethods, RoomMethods,
                UserDataMethods, ModuleMethods):
    """
    ClientAPI is a medium-level wrapper around the HTTPAPI that provides many easy-to-use
    functions for accessing the client-server API.
    """
