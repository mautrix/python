# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from mautrix.client.state_store.sqlalchemy import SQLStateStore as SQLClientStateStore

from .memory import ASStateStore


class SQLASStateStore(SQLClientStateStore, ASStateStore):
    def __init__(self) -> None:
        SQLClientStateStore.__init__(self)
        ASStateStore.__init__(self)
