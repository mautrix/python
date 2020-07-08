# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Type, Dict, Tuple, List, Any, TYPE_CHECKING
import logging
import pickle
import time

from mautrix.types import DeviceID, SyncToken, IdentityKey, SessionID, EventID, UserID, RoomID
from mautrix.util.logging import TraceLogger

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


class PickleCryptoStore(MemoryCryptoStore):
    log: TraceLogger
    path: str
    save_interval: float
    _last_save: float

    def __init__(self, account_id: str, pickle_key: str, path: str, save_interval: float = 60.0,
                 log: Optional[TraceLogger] = None) -> None:
        super().__init__(account_id, pickle_key)
        self.path = path
        self._last_save = time.monotonic()
        self.save_interval = save_interval
        self.log = log or logging.getLogger("mau.crypto.pickle")

    async def start(self) -> None:
        try:
            with open(self.path, "rb") as file:
                data: 'PickledStore' = pickle.load(file)
        except FileNotFoundError:
            return
        self.log.debug(f"Reading data in pickled crypto store {self.path}")
        if data.get("version", 0) != 1:
            raise ValueError("Unsupported pickled crypto store version")
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

    async def flush(self) -> None:
        self.log.debug(f"Writing data to pickled crypto store {self.path}")
        data: 'PickledStore' = {
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
        with open(self.path, "wb") as file:
            pickle.dump(data, file)

    async def _time_limited_flush(self) -> None:
        if self._last_save + self.save_interval < time.monotonic():
            await self.flush()
            self._last_save = time.monotonic()

    async def put_device_id(self, device_id: DeviceID) -> None:
        await super().put_device_id(device_id)
        await self._time_limited_flush()

    async def put_next_batch(self, next_batch: SyncToken) -> None:
        await super().put_next_batch(next_batch)
        await self._time_limited_flush()

    async def put_account(self, account: OlmAccount) -> None:
        await super().put_account(account)
        await self.flush()

    async def add_session(self, key: IdentityKey, session: Session) -> None:
        await super().add_session(key, session)
        await self._time_limited_flush()

    async def put_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID, session: InboundGroupSession) -> None:
        await super().put_group_session(room_id, sender_key, session_id, session)
        await self._time_limited_flush()

    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None:
        await super().add_outbound_group_session(session)
        await self._time_limited_flush()

    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None:
        await super().update_outbound_group_session(session)
        await self._time_limited_flush()

    async def remove_outbound_group_session(self, room_id: RoomID) -> None:
        await super().remove_outbound_group_session(room_id)
        await self._time_limited_flush()

    async def put_devices(self, user_id: UserID, devices: Dict[DeviceID, DeviceIdentity]) -> None:
        await super().put_devices(user_id, devices)
        await self._time_limited_flush()
