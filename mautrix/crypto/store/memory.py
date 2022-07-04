# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.client.state_store import SyncStore
from mautrix.types import (
    CrossSigner,
    CrossSigningUsage,
    DeviceID,
    DeviceIdentity,
    EventID,
    IdentityKey,
    RoomID,
    SessionID,
    SigningKey,
    SyncToken,
    TOFUSigningKey,
    UserID,
)

from ..account import OlmAccount
from ..sessions import InboundGroupSession, OutboundGroupSession, Session
from .abstract import CryptoStore


class MemoryCryptoStore(CryptoStore, SyncStore):
    _device_id: DeviceID | None
    _sync_token: SyncToken | None
    _account: OlmAccount | None
    _message_indices: dict[tuple[IdentityKey, SessionID, int], tuple[EventID, int]]
    _devices: dict[UserID, dict[DeviceID, DeviceIdentity]]
    _olm_sessions: dict[IdentityKey, list[Session]]
    _inbound_sessions: dict[tuple[RoomID, SessionID], InboundGroupSession]
    _outbound_sessions: dict[RoomID, OutboundGroupSession]
    _signatures: dict[CrossSigner, dict[CrossSigner, str]]
    _cross_signing_keys: dict[UserID, dict[CrossSigningUsage, TOFUSigningKey]]

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
        self._signatures = {}
        self._cross_signing_keys = {}

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
        self._inbound_sessions[(room_id, session_id)] = session

    async def get_group_session(
        self, room_id: RoomID, session_id: SessionID
    ) -> InboundGroupSession:
        return self._inbound_sessions.get((room_id, session_id))

    async def has_group_session(self, room_id: RoomID, session_id: SessionID) -> bool:
        return (room_id, session_id) in self._inbound_sessions

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

    async def put_cross_signing_key(
        self, user_id: UserID, usage: CrossSigningUsage, key: SigningKey
    ) -> None:
        try:
            current = self._cross_signing_keys[user_id][usage]
        except KeyError:
            self._cross_signing_keys.setdefault(user_id, {})[usage] = TOFUSigningKey(
                key=key, first=key
            )
        else:
            current.key = key

    async def get_cross_signing_keys(
        self, user_id: UserID
    ) -> dict[CrossSigningUsage, TOFUSigningKey]:
        return self._cross_signing_keys.get(user_id, {})

    async def put_signature(
        self, target: CrossSigner, signer: CrossSigner, signature: str
    ) -> None:
        self._signatures.setdefault(signer, {})[target] = signature

    async def is_key_signed_by(self, target: CrossSigner, signer: CrossSigner) -> bool:
        return target in self._signatures.get(signer, {})

    async def drop_signatures_by_key(self, signer: CrossSigner) -> int:
        deleted = self._signatures.pop(signer, None)
        return len(deleted)
