# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .account_data import AccountDataMethods
from .crypto import CryptoMethods
from .media_repository import MediaRepositoryMethods
from .misc import MiscModuleMethods
from .push_rules import PushRuleMethods
from .room_tag import RoomTaggingMethods


class ModuleMethods(
    MediaRepositoryMethods,
    CryptoMethods,
    AccountDataMethods,
    MiscModuleMethods,
    RoomTaggingMethods,
    PushRuleMethods,
):
    """
    Methods in section 13 Modules of the spec.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1.html#modules>`__
    """

    # TODO: subregions 15, 21, 26, 27, others?
