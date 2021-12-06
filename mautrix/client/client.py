# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix import __optional_imports__
from mautrix.types import Event, EventType, StateEvent

from .encryption_manager import DecryptionDispatcher, EncryptingAPI
from .state_store import StateStore, SyncStore
from .syncer import Syncer

if __optional_imports__:
    from .. import crypto as crypt


class Client(EncryptingAPI, Syncer):
    """Client is a high-level wrapper around the client API."""

    def __init__(
        self,
        *args,
        sync_store: SyncStore | None = None,
        state_store: StateStore | None = None,
        **kwargs,
    ) -> None:
        EncryptingAPI.__init__(self, *args, state_store=state_store, **kwargs)
        Syncer.__init__(self, sync_store)
        self.add_event_handler(EventType.ALL, self._update_state)

    async def _update_state(self, evt: Event) -> None:
        if not isinstance(evt, StateEvent) or not self.state_store:
            return
        await self.state_store.update_state(evt)

    @EncryptingAPI.crypto.setter
    def crypto(self, crypto: crypt.OlmMachine | None) -> None:
        """
        Set the olm machine and enable the automatic event decryptor.

        Args:
            crypto: The olm machine to use for crypto

        Raises:
            ValueError: if :attr:`state_store` is not set.
        """
        if not self.state_store:
            raise ValueError("State store must be set to use encryption")
        self._crypto = crypto
        if self.crypto_enabled:
            self.add_dispatcher(DecryptionDispatcher)
        else:
            self.remove_dispatcher(DecryptionDispatcher)
