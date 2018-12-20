# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .media_repository import MediaRepositoryMethods
from .misc import MiscModuleMethods


class ModuleMethods(MediaRepositoryMethods, MiscModuleMethods):
    """
    Methods in section 13 Modules of the spec.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#modules>`__
    """

    # TODO: subregions 15, 18, 19, 21, 26, 27, others?
