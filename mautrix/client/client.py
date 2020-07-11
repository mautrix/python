# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, TYPE_CHECKING

from .api import ClientAPI
from .state_store import SyncStore, StateStore, MemoryStateStore
from .syncer import Syncer
from .store_updater import StoreUpdatingAPI

if TYPE_CHECKING:
    from mautrix.crypto import OlmMachine


class Client(StoreUpdatingAPI, Syncer):
    """Client is a high-level wrapper around the client API."""

    state_store: StateStore
    crypto: Optional['OlmMachine']

    def __init__(self, *args, sync_store: SyncStore = None, state_store: StateStore = None,
                 crypto: 'OlmMachine' = None, **kwargs):
        ClientAPI.__init__(self, *args, **kwargs)
        Syncer.__init__(self, sync_store)

        self.state_store = state_store or MemoryStateStore()
        self.crypto = crypto
