# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Optional, Tuple
from abc import ABC
import time

from mautrix.client.state_store import StateStore as ClientStateStore
from mautrix.types import EventID, RoomID, UserID


class ASStateStore(ClientStateStore, ABC):
    _presence: Dict[UserID, str]
    _typing: Dict[Tuple[RoomID, UserID], int]
    _read: Dict[Tuple[RoomID, UserID], EventID]
    _registered: Dict[UserID, bool]

    def __init__(self) -> None:
        self._registered = {}
        # Non-persistent storage
        self._presence = {}
        self._typing = {}
        self._read = {}

    async def is_registered(self, user_id: UserID) -> bool:
        """
        Check if a given user is registered.

        This should always return ``True`` for double puppets, because they're always registered
        beforehand and shouldn't be attempted to register by the bridge.

        Args:
            user_id: The user ID to check.

        Returns:
            ``True`` if the user is registered, ``False`` otherwise.
        """
        if not user_id:
            raise ValueError("user_id is empty")
        return self._registered.get(user_id, False)

    async def registered(self, user_id: UserID) -> None:
        """
        Mark the given user ID as registered.

        Args:
            user_id: The user ID to mark as registered.
        """
        if not user_id:
            raise ValueError("user_id is empty")
        self._registered[user_id] = True

    def set_presence(self, user_id: UserID, presence: str) -> None:
        self._presence[user_id] = presence

    def has_presence(self, user_id: UserID, presence: str) -> bool:
        try:
            return self._presence[user_id] == presence
        except KeyError:
            return False

    def set_read(self, room_id: RoomID, user_id: UserID, event_id: EventID) -> None:
        self._read[(room_id, user_id)] = event_id

    def get_read(self, room_id: RoomID, user_id: UserID) -> Optional[EventID]:
        try:
            return self._read[(room_id, user_id)]
        except KeyError:
            return None

    def set_typing(
        self, room_id: RoomID, user_id: UserID, is_typing: bool, timeout: int = 0
    ) -> None:
        if is_typing:
            ts = int(round(time.time() * 1000))
            self._typing[(room_id, user_id)] = ts + timeout
        else:
            try:
                del self._typing[(room_id, user_id)]
            except KeyError:
                pass

    def is_typing(self, room_id: RoomID, user_id: UserID) -> bool:
        ts = int(round(time.time() * 1000))
        try:
            return self._typing[(room_id, user_id)] > ts
        except KeyError:
            return False
