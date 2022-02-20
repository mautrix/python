# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from mautrix.client.state_store.asyncpg import PgStateStore as PgClientStateStore
from mautrix.util.async_db import Database

from .memory import ASStateStore


class PgASStateStore(PgClientStateStore, ASStateStore):
    def __init__(self, db: Database) -> None:
        PgClientStateStore.__init__(self, db)
        ASStateStore.__init__(self)
