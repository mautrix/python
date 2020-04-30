# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, List, Set, Iterable, Dict, Any
from datetime import datetime

from sqlalchemy import Column, PickleType, LargeBinary, String, Boolean, DateTime, Text, select
from sqlalchemy.engine.base import Engine
from nio.crypto import (OlmAccount, SessionStore, GroupSessionStore, DeviceStore, Session,
                        InboundGroupSession, OlmDevice, OutgoingKeyRequest)

from mautrix.util.db import Base
from mautrix.types import UserID, RoomID, SyncToken


class DBAccount(Base):
    __tablename__ = "nio_account"

    user_id: UserID = Column(String(255), primary_key=True)
    device_id: str = Column(String(255), primary_key=True)
    shared: bool = Column(Boolean, nullable=False)
    sync_token: SyncToken = Column(Text, nullable=False)
    account: bytes = Column(LargeBinary, nullable=False)

    @classmethod
    def first_device_id(cls, user_id: UserID) -> Optional[str]:
        acc = cls._select_one_or_none(cls.c.user_id == user_id)
        if not acc:
            return None
        return acc.device_id

    @classmethod
    def get(cls, user_id: UserID, device_id: str) -> Optional['DBAccount']:
        return cls._select_one_or_none((cls.c.user_id == user_id) & (cls.c.device_id == device_id))

    @classmethod
    def set_sync_token(cls, sync_token: SyncToken) -> None:
        with cls.db.begin() as conn:
            conn.execute(cls.t.update().values(sync_token=sync_token))

    @classmethod
    def get_sync_token(cls) -> Optional[SyncToken]:
        rows = cls.db.execute(select([cls.c.sync_token]))
        try:
            return SyncToken(next(rows)[0])
        except (StopIteration, IndexError):
            return None


class DBOlmSession(Base):
    __tablename__ = "nio_olm_session"

    session_id: str = Column(String(255), primary_key=True)
    sender_key: str = Column(String(255), nullable=False)
    session: bytes = Column(LargeBinary, nullable=False)
    created_at: datetime = Column(DateTime, nullable=False)
    last_used: datetime = Column(DateTime, nullable=False)

    @classmethod
    def all(cls) -> Iterable['DBOlmSession']:
        return cls._select_all()


class DBDeviceKey(Base):
    __tablename__ = "nio_device_key"

    user_id: UserID = Column(String(255), primary_key=True)
    device_id: str = Column(String(255), primary_key=True)
    display_name: str = Column(String(255), nullable=False)
    deleted: bool = Column(Boolean, nullable=False)
    keys: Dict[str, str] = Column(PickleType, nullable=False)

    @classmethod
    def all(cls) -> Iterable['DBDeviceKey']:
        return cls._select_all()

    @classmethod
    def insert_many(cls, data: List[Dict[str, Any]]) -> None:
        cls.db.execute(cls.t.insert(), data)


class DBMegolmInboundSession(Base):
    __tablename__ = "nio_megolm_inbound_session"

    session_id: str = Column(String(255), primary_key=True)
    sender_key: str = Column(String(255), nullable=False)
    fp_key: str = Column(String(255), nullable=False)
    room_id: RoomID = Column(String(255), nullable=False)
    session: bytes = Column(LargeBinary, nullable=False)
    forwarded_chains: List[str] = Column(PickleType, nullable=False)

    @classmethod
    def all(cls) -> Iterable['DBMegolmInboundSession']:
        return cls._select_all()


class DBOutgoingKeyRequest(Base):
    __tablename__ = "nio_outgoing_key_request"

    request_id: str = Column(String(255), primary_key=True)
    session_id: str = Column(String(255), nullable=False)
    room_id: RoomID = Column(String(255), nullable=False)
    algorithm: str = Column(String(255), nullable=False)

    @classmethod
    def all(cls) -> Iterable['DBOutgoingKeyRequest']:
        return cls._select_all()

    @classmethod
    def delete_by_id(cls, request_id: str) -> None:
        with cls.db.begin() as conn:
            conn.execute(cls.t.delete().where(cls.c.request_id == request_id))


def init(db_engine: Engine) -> None:
    for table in (DBAccount, DBOlmSession, DBDeviceKey, DBMegolmInboundSession,
                  DBOutgoingKeyRequest):
        table.db = db_engine
        table.t = table.__table__
        table.c = table.t.c
        table.column_names = table.c.keys()


class NioStore:
    user_id: UserID
    device_id: str
    pickle_key: str

    def __init__(self, user_id: UserID, device_id: str, store_path: str, pickle_key: str,
                 store_name: str) -> None:
        self.user_id = user_id
        self.device_id = device_id
        self.pickle_key = pickle_key

    def load_account(self) -> Optional[OlmAccount]:
        """Load the Olm account from the database.

        Returns:
            ``OlmAccount`` object, or ``None`` if it wasn't found for the
                current device_id.

        """
        account = DBAccount.get(self.user_id, self.device_id)
        if not account:
            return None

        return OlmAccount.from_pickle(account.account, self.pickle_key, account.shared)

    def save_account(self, account: OlmAccount) -> None:
        """Save the provided Olm account to the database.

        Args:
            account (OlmAccount): The olm account that will be pickled and
                saved in the database.
        """
        DBAccount(user_id=self.user_id, device_id=self.device_id, shared=account.shared,
                  account=account.pickle(self.pickle_key), sync_token=SyncToken("")).upsert()

    def load_sessions(self) -> SessionStore:
        """Load all Olm sessions from the database.

        Returns:
            ``SessionStore`` object, containing all the loaded sessions.

        """
        session_store = SessionStore()
        for session in DBOlmSession.all():
            session_store.add(session.sender_key, Session.from_pickle(session.session,
                                                                      session.created_at,
                                                                      self.pickle_key))
        return session_store

    def save_session(self, curve_key: str, session: Session) -> None:
        """Save the provided Olm session to the database.

        Args:
            curve_key (str): The curve key that owns the Olm session.
            session (Session): The Olm session that will be pickled and
                saved in the database.
        """
        DBOlmSession(session_id=session.id, sender_key=curve_key, created_at=session.creation_time,
                     last_used=session.use_time, session=session.pickle(self.pickle_key)).upsert()

    def load_inbound_group_sessions(self) -> GroupSessionStore:
        """Load all Olm sessions from the database.

        Returns:
            ``GroupSessionStore`` object, containing all the loaded sessions.

        """
        store = GroupSessionStore()

        for session in DBMegolmInboundSession.all():
            store.add(InboundGroupSession.from_pickle(session.session, session.fp_key,
                                                      session.sender_key, session.room_id,
                                                      self.pickle_key, session.forwarded_chains))

        return store

    def save_inbound_group_session(self, session: InboundGroupSession) -> None:
        """Save the provided Megolm inbound group session to the database.

        Args:
            session (InboundGroupSession): The session to save.
        """
        DBMegolmInboundSession(session_id=session.id, sender_key=session.sender_key,
                               fp_key=session.ed25519, room_id=RoomID(session.room_id),
                               session=session.pickle(self.pickle_key),
                               forwarded_chains=session.forwarding_chain).upsert()

    @staticmethod
    def load_device_keys() -> DeviceStore:
        """Load all the device keys from the database.

        Returns DeviceStore containing the OlmDevices with the device keys.
        """
        store = DeviceStore()
        for device_key in DBDeviceKey.all():
            store.add(OlmDevice(device_key.user_id, device_key.device_id, device_key.keys,
                                display_name=device_key.display_name, deleted=device_key.deleted))
        return store

    @staticmethod
    def save_device_keys(device_keys: Dict[str, Dict[str, OlmDevice]]) -> None:
        """Save the provided device keys to the database.

        Args:
            device_keys: A dictionary
                containing a mapping from a user id to a dictionary containing
                a mapping of a device id to a OlmDevice.
        """
        for user_id, devices_dict in device_keys.items():
            for device_id, device in devices_dict.items():
                DBDeviceKey(user_id=UserID(user_id), device_id=device_id, keys=device.keys,
                            display_name=device.display_name, deleted=device.deleted).upsert()

    @staticmethod
    def load_encrypted_rooms() -> Set[str]:
        """Load the set of encrypted rooms for this account.

        Returns:
            ``Set`` containing room ids of encrypted rooms.

        """
        return set()

    @staticmethod
    def load_outgoing_key_requests() -> Dict[str, OutgoingKeyRequest]:
        """Load the set of outgoing key requests for this account.

        Returns:
            ``Set`` containing request ids of key requests.

        """
        return {request.request_id: OutgoingKeyRequest.from_database(request)
                for request in DBOutgoingKeyRequest.all()}

    @staticmethod
    def add_outgoing_key_request(key_request: OutgoingKeyRequest) -> None:
        """Add an outgoing key request to the store."""
        DBOutgoingKeyRequest(
            request_id=key_request.request_id,
            session_id=key_request.session_id,
            room_id=key_request.room_id,
            algorithm=key_request.algorithm,
        ).upsert()

    @staticmethod
    def remove_outgoing_key_request(key_request: OutgoingKeyRequest) -> None:
        """Remove an active outgoing key request from the store."""
        DBOutgoingKeyRequest.delete_by_id(key_request.request_id)

    def save_encrypted_rooms(self, rooms: Set[str]) -> None:
        """Save the set of room ids for this account."""
        pass

    def delete_encrypted_room(self, room: str) -> None:
        """Delete the a encrypted room from the store."""
        pass

    @staticmethod
    def save_sync_token(token: SyncToken) -> None:
        """Save the given token"""
        DBAccount.set_sync_token(token)

    @staticmethod
    def load_sync_token() -> Optional[SyncToken]:
        return DBAccount.get_sync_token()

    def blacklist_device(self, device: OlmDevice) -> bool:
        """Mark a device as blacklisted.

        Args:
            device (OlmDevice): The device that will be marked as blacklisted

        Returns True if the device was blacklisted, False otherwise, e.g. if
        the device was already blacklisted.

        """
        return False

    def unblacklist_device(self, device: OlmDevice) -> bool:
        """Unmark a device as blacklisted.

        Args:
            device (OlmDevice): The device that will be unmarked as blacklisted

        """
        return False

    def verify_device(self, device: OlmDevice) -> bool:
        """Mark a device as verified.

        Args:
            device (OlmDevice): The device that will be marked as verified

        Returns True if the device was verified, False otherwise, e.g. if the
        device was already verified.

        """
        return False

    def is_device_verified(self, device: OlmDevice) -> bool:
        """Check if a device is verified.

        Args:
            device (OlmDevice): The device that will be checked if it's
                verified.
        """
        return True

    def is_device_blacklisted(self, device: OlmDevice) -> bool:
        """Check if a device is blacklisted.

        Args:
            device (OlmDevice): The device that will be checked if it's
                blacklisted.
        """
        return False

    def unverify_device(self, device: OlmDevice) -> bool:
        """Unmark a device as verified.

        Args:
            device (OlmDevice): The device that will be unmarked as verified

        Returns True if the device was unverified, False otherwise, e.g. if the
        device wasn't verified.

        """
        return False

    def ignore_device(self, device: OlmDevice) -> bool:
        """Mark a device as ignored.

        Args:
            device (OlmDevice): The device that will be marked as blacklisted

        Returns True if the device was ignored, False otherwise, e.g. if
        the device was already ignored.
        """
        return False

    def unignore_device(self, device: OlmDevice) -> bool:
        """Unmark a device as ignored.

        Args:
            device (OlmDevice): The device that will be marked as blacklisted

        Returns True if the device was unignored, False otherwise, e.g. if the
        device wasn't ignored in the first place.
        """
        return False

    def ignore_devices(self, devices: List[OlmDevice]) -> None:
        """Mark a list of devices as ignored.

        This is a more efficient way to mark multiple devices as ignored.

        Args:
            device (list[OlmDevice]): A list of OlmDevices that will be marked
                as ignored.

        """
        pass

    def is_device_ignored(self, device: OlmDevice) -> bool:
        """Check if a device is ignored.

        Args:
            device (OlmDevice): The device that will be checked if it's
                ignored.
        """
        return True
