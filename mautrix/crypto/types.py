# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import cast, Optional, Union, List, Set, Tuple
from datetime import datetime, timedelta
from enum import IntEnum

from attr import dataclass
import olm

from mautrix.types import UserID, DeviceID, IdentityKey, SigningKey, RoomID


class EncryptionError(Exception):
    pass


class TrustState(IntEnum):
    UNSET = 0
    VERIFIED = 1
    BLACKLISTED = 2
    IGNORED = 3


@dataclass
class DeviceIdentity:
    user_id: UserID
    device_id: DeviceID
    identity_key: IdentityKey
    signing_key: SigningKey

    trust: TrustState
    deleted: bool
    name: str


class OlmAccount(olm.Account):
    shared: bool

    def __init__(self) -> None:
        super().__init__()
        self.shared = False

    @classmethod
    def from_pickle(cls, pickle: bytes, passphrase: str, shared: bool) -> 'OlmAccount':
        account = cast(OlmAccount, super().from_pickle(pickle, passphrase))
        account.shared = shared
        return account

    def new_inbound_session(self, sender_key: IdentityKey, ciphertext: str) -> 'Session':
        session = olm.InboundSession(self, olm.OlmPreKeyMessage(ciphertext), sender_key)
        self.remove_one_time_keys(session)
        return Session.from_pickle(session.pickle("roundtrip"), passphrase="roundtrip",
                                   creation_time=datetime.now())

    def new_outbound_session(self, target_key: IdentityKey, one_time_key: IdentityKey) -> 'Session':
        session = olm.OutboundSession(self, target_key, one_time_key)
        return Session.from_pickle(session.pickle("roundtrip"), passphrase="roundtrip",
                                   creation_time=datetime.now())


class Session(olm.Session):
    creation_time: datetime
    use_time: datetime

    def __init__(self):
        super().__init__()
        self.creation_time = datetime.now()
        self.use_time = datetime.now()

    def __new__(cls, *args):
        return super().__new__(cls)

    @property
    def expired(self):
        return False

    @classmethod
    def from_pickle(cls, pickle: bytes, passphrase: str, creation_time: datetime,
                    use_time: Optional[datetime] = None) -> 'Session':
        session = super().from_pickle(pickle, passphrase=passphrase)
        session.creation_time = creation_time
        session.use_time = use_time or creation_time
        return session

    def decrypt(self, ciphertext: olm.OlmMessage, unicode_errors: str = "replace") -> str:
        self.use_time = datetime.now()
        return super().decrypt(ciphertext)

    def encrypt(self, plaintext: str) -> Union[olm.OlmMessage, olm.OlmPreKeyMessage]:
        self.use_time = datetime.now()
        return super().encrypt(plaintext)


class InboundGroupSession(olm.InboundGroupSession):
    room_id: RoomID
    signing_key: SigningKey
    sender_key: IdentityKey
    forwarding_chain: List[str]

    def __init__(self, session_key: str, signing_key: SigningKey, sender_key: IdentityKey,
                 room_id: RoomID, forwarding_chain: Optional[List[str]] = None) -> None:
        self.signing_key = signing_key
        self.sender_key = sender_key
        self.room_id = room_id
        self.forwarding_chain = forwarding_chain or []
        super().__init__(session_key)

    def __new__(cls, *args):
        return super().__new__(cls)

    @classmethod
    def from_pickle(cls, pickle: bytes, passphrase: str, signing_key: SigningKey,
                    sender_key: IdentityKey, room_id: RoomID,
                    forwarding_chain: Optional[List[str]] = None) -> 'InboundGroupSession':
        session = super().from_pickle(pickle, passphrase)
        session.ed25519 = signing_key
        session.sender_key = sender_key
        session.room_id = room_id
        session.forwarding_chain = forwarding_chain or []
        return session

    @classmethod
    def import_session(cls, session_key: str, signing_key: SigningKey, sender_key: IdentityKey,
                       room_id: RoomID, forwarding_chain: Optional[List[str]] = None
                       ) -> 'InboundGroupSession':
        session = super().import_session(session_key)
        session.ed25519 = signing_key
        session.sender_key = sender_key
        session.room_id = room_id
        session.forwarding_chain = forwarding_chain or []
        return session


class OutboundGroupSession(olm.OutboundGroupSession):
    """Outbound group session aware of the users it is shared with.

    Also remembers the time it was created and the number of messages it has
    encrypted, in order to know if it needs to be rotated.
    """

    max_age: timedelta
    max_messages: int
    creation_time: datetime
    use_time: datetime
    message_count: int

    room_id: RoomID
    users_shared_with: Set[Tuple[UserID, DeviceID]]
    users_ignored: Set[Tuple[UserID, DeviceID]]
    shared: bool

    def __init__(self, room_id: RoomID) -> None:
        self.max_age = timedelta(days=7)
        self.max_messages = 100
        self.creation_time = datetime.now()
        self.use_time = datetime.now()
        self.message_count = 0
        self.room_id = room_id
        self.users_shared_with = set()
        self.users_ignored = set()
        self.shared = False
        super().__init__()

    def __new__(cls, **kwargs):
        return super().__new__(cls)

    @property
    def expired(self):
        return (self.message_count >= self.max_messages
                or datetime.now() - self.creation_time >= self.max_age)

    def encrypt(self, plaintext):
        if not self.shared:
            raise EncryptionError("Session is not shared")

        if self.expired:
            raise EncryptionError("Session has expired")

        self.message_count += 1
        self.use_time = datetime.now()
        return super().encrypt(plaintext)

    @classmethod
    def from_pickle(cls, pickle: bytes, passphrase: str, max_age: timedelta, max_messages: int,
                    creation_time: datetime, use_time: datetime, message_count: int,
                    room_id: RoomID, shared: bool) -> 'OutboundGroupSession':
        session = cast(OutboundGroupSession, super().from_pickle(pickle, passphrase))
        session.max_age = max_age
        session.max_messages = max_messages
        session.creation_time = creation_time
        session.use_time = use_time
        session.message_count = message_count
        session.room_id = room_id
        session.users_shared_with = set()
        session.users_ignored = set()
        session.shared = shared
        return session
