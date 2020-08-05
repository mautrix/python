# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Optional, List, Tuple

from mautrix.types import SyncToken, IdentityKey, SessionID, RoomID, EventID, UserID, DeviceID
from mautrix.client.state_store import SyncStore

from .. import OlmAccount, Session, InboundGroupSession, OutboundGroupSession, DeviceIdentity
from .abstract import CryptoStore


class MemoryCryptoStore(CryptoStore, SyncStore):
    _device_id: Optional[DeviceID]
    _sync_token: Optional[SyncToken]
    _account: Optional[OlmAccount]
    _message_indices: Dict[Tuple[IdentityKey, SessionID, int], Tuple[EventID, int]]
    _devices: Dict[UserID, Dict[DeviceID, DeviceIdentity]]
    _olm_sessions: Dict[IdentityKey, List[Session]]
    _inbound_sessions: Dict[Tuple[RoomID, IdentityKey, SessionID], InboundGroupSession]
    _outbound_sessions: Dict[RoomID, OutboundGroupSession]

    def __init__(self, account_id: str, pickle_key: str) -> None:
        self.account_id = account_id
        self.pickle_key = pickle_key

        self._sync_token = None
        self._device_id = None
        self._account = None
        self._message_indices = {}
        self._devices = {}
        self._olm_sessions = {}
        self._inbound_sessions = {}
        self._outbound_sessions = {}

    async def get_device_id(self) -> Optional[DeviceID]:
        return self._device_id

    async def put_device_id(self, device_id: DeviceID) -> None:
        self._device_id = device_id

    async def put_next_batch(self, next_batch: SyncToken) -> None:
        self._sync_token = next_batch

    async def get_next_batch(self) -> SyncToken:
        return self._sync_token

    async def put_account(self, account: OlmAccount) -> None:
        self._account = account

    async def get_account(self) -> OlmAccount:
        return self._account

    async def has_session(self, key: IdentityKey) -> bool:
        return key in self._olm_sessions

    async def get_sessions(self, key: IdentityKey) -> List[Session]:
        return self._olm_sessions.get(key, [])

    async def get_latest_session(self, key: IdentityKey) -> Optional[Session]:
        try:
            return self._olm_sessions[key][-1]
        except (KeyError, IndexError):
            return None

    async def add_session(self, key: IdentityKey, session: Session) -> None:
        self._olm_sessions.setdefault(key, []).append(session)

    async def update_session(self, key: IdentityKey, session: Session) -> None:
        # This is a no-op as the session object is the same one previously added.
        pass

    async def put_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID, session: InboundGroupSession) -> None:
        self._inbound_sessions[(room_id, sender_key, session_id)] = session

    async def get_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID) -> InboundGroupSession:
        return self._inbound_sessions.get((room_id, sender_key, session_id))

    async def has_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID) -> bool:
        return (room_id, sender_key, session_id) in self._inbound_sessions

    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None:
        self._outbound_sessions[session.room_id] = session

    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None:
        # This is a no-op as the session object is the same one previously added.
        pass

    async def get_outbound_group_session(self, room_id: RoomID) -> Optional[OutboundGroupSession]:
        return self._outbound_sessions.get(room_id)

    async def remove_outbound_group_session(self, room_id: RoomID) -> None:
        self._outbound_sessions.pop(room_id, None)

    async def remove_outbound_group_sessions(self, rooms: List[RoomID]) -> None:
        for room_id in rooms:
            self._outbound_sessions.pop(room_id, None)

    async def validate_message_index(self, sender_key: IdentityKey, session_id: SessionID,
                                     event_id: EventID, index: int, timestamp: int) -> bool:
        try:
            return self._message_indices[(sender_key, session_id, index)] == (event_id, timestamp)
        except KeyError:
            self._message_indices[(sender_key, session_id, index)] = (event_id, timestamp)
            return True

    async def get_devices(self, user_id: UserID) -> Optional[Dict[DeviceID, DeviceIdentity]]:
        return self._devices.get(user_id)

    async def get_device(self, user_id: UserID, device_id: DeviceID) -> Optional[DeviceIdentity]:
        return self._devices.get(user_id, {}).get(device_id)

    async def put_devices(self, user_id: UserID, devices: Dict[DeviceID, DeviceIdentity]) -> None:
        self._devices[user_id] = devices

    async def filter_tracked_users(self, users: List[UserID]) -> List[UserID]:
        return [user_id for user_id in users if user_id in self._devices]
