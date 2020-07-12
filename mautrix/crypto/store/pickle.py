# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Type, Dict, Tuple, List, Any, TYPE_CHECKING

from mautrix.types import DeviceID, SyncToken, IdentityKey, SessionID, EventID, UserID, RoomID
from mautrix.util.file_store import FileStore

from .. import OlmAccount, Session, InboundGroupSession, OutboundGroupSession, DeviceIdentity
from .memory import MemoryCryptoStore

if TYPE_CHECKING:
    from typing import Protocol, TypedDict, TypeVar

    T = TypeVar('T')


    class Pickled(TypedDict, total=False):
        pickle: bytes


    class PickledStore(TypedDict):
        version: int
        device_id: DeviceID
        sync_token: SyncToken
        account: Pickled
        message_indices: Dict[Tuple[IdentityKey, SessionID, int], Tuple[EventID, int]]
        devices: Dict[UserID, Dict[DeviceID, DeviceIdentity]]
        olm_sessions: Dict[IdentityKey, List[Pickled]]
        inbound_sessions: Dict[Tuple[RoomID, IdentityKey, SessionID], Pickled]
        outbound_sessions: Dict[RoomID, Pickled]


    class Picklable(Protocol[T]):
        @classmethod
        def from_pickle(cls, pickle: bytes, passphrase: str, **kwargs: Any) -> T: ...

        def pickle(self, passphrase: str) -> bytes: ...


class PickleCryptoStore(FileStore, MemoryCryptoStore):
    path: str
    save_interval: float
    _last_save: float

    def __init__(self, account_id: str, pickle_key: str, path: str, save_interval: float = 60.0
                 ) -> None:
        FileStore.__init__(self, path=path, save_interval=save_interval, binary=True)
        MemoryCryptoStore.__init__(self, account_id, pickle_key)

    def deserialize(self, data: 'PickledStore') -> None:
        if data.get("version", 0) != 1:
            raise ValueError("Unsupported file crypto store version")
        self._device_id = data["device_id"]
        self._sync_token = data["sync_token"]
        self._account = self._from_pickle(OlmAccount, data["account"])
        self._message_indices = data["message_indices"]
        self._devices = data["devices"]
        self._olm_sessions = {identity_key: [self._from_pickle(Session, session)
                                             for session in sessions]
                              for identity_key, sessions in data["olm_sessions"].items()}
        self._inbound_sessions = {key: self._from_pickle(InboundGroupSession, session)
                                  for key, session in data["inbound_sessions"].items()}
        self._outbound_sessions = {room_id: self._from_pickle(OutboundGroupSession, session)
                                   for room_id, session in data["outbound_sessions"].items()}

    def _from_pickle(self, entity_type: Type['Picklable[T]'], data: 'Pickled') -> 'T':
        pickle_data = data.pop("pickle")
        return entity_type.from_pickle(pickle_data, passphrase=self.pickle_key, **data)

    def serialize(self) -> 'PickledStore':
        return {
            "version": 1,
            "device_id": self._device_id,
            "sync_token": self._sync_token,
            "account": {
                "pickle": self._account.pickle(self.pickle_key),
                "shared": self._account.shared
            },
            "message_indices": self._message_indices,
            "devices": self._devices,
            "olm_sessions": {identity_key: [{"pickle": session.pickle(self.pickle_key),
                                             "creation_time": session.creation_time,
                                             "use_time": session.use_time}
                                            for session in sessions]
                             for identity_key, sessions in self._olm_sessions.items()},
            "inbound_sessions": {key: {"pickle": session.pickle(self.pickle_key),
                                       "room_id": session.room_id,
                                       "sender_key": session.sender_key,
                                       "signing_key": session.signing_key,
                                       "forwarding_chain": session.forwarding_chain}
                                 for key, session in self._inbound_sessions.items()},
            "outbound_sessions": {room_id: {"pickle": session.pickle(self.pickle_key),
                                            "max_age": session.max_age,
                                            "max_messages": session.max_messages,
                                            "creation_time": session.creation_time,
                                            "use_time": session.use_time,
                                            "message_count": session.message_count,
                                            "room_id": session.room_id,
                                            "shared": session.shared}
                                  for room_id, session in self._outbound_sessions.items()}
        }

    async def put_device_id(self, device_id: DeviceID) -> None:
        await super().put_device_id(device_id)
        self._time_limited_flush()

    async def put_next_batch(self, next_batch: SyncToken) -> None:
        await super().put_next_batch(next_batch)
        self._time_limited_flush()

    async def put_account(self, account: OlmAccount) -> None:
        await super().put_account(account)
        self._save()

    async def add_session(self, key: IdentityKey, session: Session) -> None:
        await super().add_session(key, session)
        self._time_limited_flush()

    async def put_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID, session: InboundGroupSession) -> None:
        await super().put_group_session(room_id, sender_key, session_id, session)
        self._time_limited_flush()

    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None:
        await super().add_outbound_group_session(session)
        self._time_limited_flush()

    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None:
        await super().update_outbound_group_session(session)
        self._time_limited_flush()

    async def remove_outbound_group_session(self, room_id: RoomID) -> None:
        await super().remove_outbound_group_session(room_id)
        self._time_limited_flush()

    async def remove_outbound_group_sessions(self, rooms: List[RoomID]) -> None:
        await super().remove_outbound_group_sessions(rooms)
        self._time_limited_flush()

    async def put_devices(self, user_id: UserID, devices: Dict[DeviceID, DeviceIdentity]) -> None:
        await super().put_devices(user_id, devices)
        self._time_limited_flush()
