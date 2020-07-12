# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, TYPE_CHECKING

from .state_store import SyncStore, StateStore
from .syncer import Syncer
from .encryption_manager import EncryptingAPI, DecryptionDispatcher

if TYPE_CHECKING:
    from mautrix.crypto import OlmMachine


class Client(EncryptingAPI, Syncer):
    """Client is a high-level wrapper around the client API."""

    def __init__(self, *args, sync_store: Optional[SyncStore] = None,
                 state_store: Optional[StateStore] = None, **kwargs) -> None:
        EncryptingAPI.__init__(self, *args, state_store=state_store, **kwargs)
        Syncer.__init__(self, sync_store)

    @EncryptingAPI.crypto.setter
    def crypto(self, crypto: 'OlmMachine') -> None:
        if not self.state_store:
            raise ValueError("State store must be set to use encryption")
        self._crypto = crypto
        if self.crypto_enabled:
            self.add_dispatcher(DecryptionDispatcher)
        else:
            self.remove_dispatcher(DecryptionDispatcher)
