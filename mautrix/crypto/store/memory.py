# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.client.state_store import SyncStore
from mautrix.types import DeviceID, EventID, IdentityKey, RoomID, SessionID, SyncToken, UserID

from .. import DeviceIdentity, InboundGroupSession, OlmAccount, OutboundGroupSession, Session
from .abstract import CryptoStore


class MemoryCryptoStore(CryptoStore, SyncStore):
    _device_id: DeviceID | None
    _sync_token: SyncToken | None
    _account: OlmAccount | None
    _message_indices: dict[tuple[IdentityKey, SessionID, int], tuple[EventID, int]]
    _devices: dict[UserID, dict[DeviceID, DeviceIdentity]]
    _olm_sessions: dict[IdentityKey, list[Session]]
    _inbound_sessions: dict[tuple[RoomID, IdentityKey, SessionID], InboundGroupSession]
    _outbound_sessions: dict[RoomID, OutboundGroupSession]

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

    async def get_device_id(self) -> DeviceID | None:
        return self._device_id

    async def put_device_id(self, device_id: DeviceID) -> None:
        self._device_id = device_id

    async def put_next_batch(self, next_batch: SyncToken) -> None:
        self._sync_token = next_batch

    async def get_next_batch(self) -> SyncToken:
        return self._sync_token

    async def delete(self) -> None:
        self._account = None
        self._device_id = None
        self._olm_sessions = {}
        self._outbound_sessions = {}

    async def put_account(self, account: OlmAccount) -> None:
        self._account = account

    async def get_account(self) -> OlmAccount:
        return self._account

    async def has_session(self, key: IdentityKey) -> bool:
        return key in self._olm_sessions

    async def get_sessions(self, key: IdentityKey) -> list[Session]:
        return self._olm_sessions.get(key, [])

    async def get_latest_session(self, key: IdentityKey) -> Session | None:
        try:
            return self._olm_sessions[key][-1]
        except (KeyError, IndexError):
            return None

    async def add_session(self, key: IdentityKey, session: Session) -> None:
        self._olm_sessions.setdefault(key, []).append(session)

    async def update_session(self, key: IdentityKey, session: Session) -> None:
        # This is a no-op as the session object is the same one previously added.
        pass

    async def put_group_session(
        self,
        room_id: RoomID,
        sender_key: IdentityKey,
        session_id: SessionID,
        session: InboundGroupSession,
    ) -> None:
        self._inbound_sessions[(room_id, sender_key, session_id)] = session

    async def get_group_session(
        self, room_id: RoomID, sender_key: IdentityKey, session_id: SessionID
    ) -> InboundGroupSession:
        return self._inbound_sessions.get((room_id, sender_key, session_id))

    async def has_group_session(
        self, room_id: RoomID, sender_key: IdentityKey, session_id: SessionID
    ) -> bool:
        return (room_id, sender_key, session_id) in self._inbound_sessions

    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None:
        self._outbound_sessions[session.room_id] = session

    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None:
        # This is a no-op as the session object is the same one previously added.
        pass

    async def get_outbound_group_session(self, room_id: RoomID) -> OutboundGroupSession | None:
        return self._outbound_sessions.get(room_id)

    async def remove_outbound_group_session(self, room_id: RoomID) -> None:
        self._outbound_sessions.pop(room_id, None)

    async def remove_outbound_group_sessions(self, rooms: list[RoomID]) -> None:
        for room_id in rooms:
            self._outbound_sessions.pop(room_id, None)

    async def validate_message_index(
        self,
        sender_key: IdentityKey,
        session_id: SessionID,
        event_id: EventID,
        index: int,
        timestamp: int,
    ) -> bool:
        try:
            return self._message_indices[(sender_key, session_id, index)] == (event_id, timestamp)
        except KeyError:
            self._message_indices[(sender_key, session_id, index)] = (event_id, timestamp)
            return True

    async def get_devices(self, user_id: UserID) -> dict[DeviceID, DeviceIdentity] | None:
        return self._devices.get(user_id)

    async def get_device(self, user_id: UserID, device_id: DeviceID) -> DeviceIdentity | None:
        return self._devices.get(user_id, {}).get(device_id)

    async def find_device_by_key(
        self, user_id: UserID, identity_key: IdentityKey
    ) -> DeviceIdentity | None:
        for device in self._devices.get(user_id, {}).values():
            if device.identity_key == identity_key:
                return device
        return None

    async def put_devices(self, user_id: UserID, devices: dict[DeviceID, DeviceIdentity]) -> None:
        self._devices[user_id] = devices

    async def filter_tracked_users(self, users: list[UserID]) -> list[UserID]:
        return [user_id for user_id in users if user_id in self._devices]
