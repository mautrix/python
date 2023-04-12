# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Optional, Set, Tuple, Union, cast
from datetime import datetime, timedelta

from _libolm import ffi, lib
from attr import dataclass
import olm

from mautrix.errors import EncryptionError
from mautrix.types import (
    DeviceID,
    EncryptionAlgorithm,
    IdentityKey,
    OlmCiphertext,
    OlmMsgType,
    RoomID,
    RoomKeyEventContent,
    SerializableAttrs,
    SigningKey,
    UserID,
    field,
)


class Session(olm.Session):
    creation_time: datetime
    last_encrypted: datetime
    last_decrypted: datetime

    def __init__(self):
        super().__init__()
        self.creation_time = datetime.now()
        self.last_encrypted = datetime.now()
        self.last_decrypted = datetime.now()

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    @property
    def expired(self):
        return False

    @classmethod
    def from_pickle(
        cls,
        pickle: bytes,
        passphrase: str,
        creation_time: datetime,
        last_encrypted: Optional[datetime] = None,
        last_decrypted: Optional[datetime] = None,
    ) -> "Session":
        session = super().from_pickle(pickle, passphrase=passphrase)
        session.creation_time = creation_time
        session.last_encrypted = last_encrypted or creation_time
        session.last_decrypted = last_decrypted or creation_time
        return session

    def matches(self, ciphertext: str) -> bool:
        return super().matches(olm.OlmPreKeyMessage(ciphertext))

    def decrypt(self, ciphertext: OlmCiphertext) -> str:
        plaintext = super().decrypt(
            olm.OlmPreKeyMessage(ciphertext.body)
            if ciphertext.type == OlmMsgType.PREKEY
            else olm.OlmMessage(ciphertext.body)
        )
        self.last_decrypted = datetime.now()
        return plaintext

    def encrypt(self, plaintext: str) -> OlmCiphertext:
        self.last_encrypted = datetime.now()
        result = super().encrypt(plaintext)
        return OlmCiphertext(
            type=(
                OlmMsgType.PREKEY
                if isinstance(result, olm.OlmPreKeyMessage)
                else OlmMsgType.MESSAGE
            ),
            body=result.ciphertext,
        )

    def describe(self) -> str:
        parent = super()
        if hasattr(parent, "describe"):
            return parent.describe()
        elif hasattr(lib, "olm_session_describe"):
            describe_length = 600
            describe_buffer = ffi.new("char[]", describe_length)
            lib.olm_session_describe(self._session, describe_buffer, describe_length)
            return ffi.string(describe_buffer).decode("utf-8")
        else:
            return "describe not supported"


@dataclass
class RatchetSafety(SerializableAttrs):
    next_index: int = 0
    missed_indices: List[int] = field(factory=lambda: [])
    lost_indices: List[int] = field(factory=lambda: [])


class InboundGroupSession(olm.InboundGroupSession):
    room_id: RoomID
    signing_key: SigningKey
    sender_key: IdentityKey
    forwarding_chain: List[IdentityKey]

    ratchet_safety: RatchetSafety
    received_at: datetime
    max_age: timedelta
    max_messages: int
    is_scheduled: bool

    def __init__(
        self,
        session_key: str,
        signing_key: SigningKey,
        sender_key: IdentityKey,
        room_id: RoomID,
        forwarding_chain: Optional[List[IdentityKey]] = None,
        ratchet_safety: Optional[RatchetSafety] = None,
        received_at: Optional[datetime] = None,
        max_age: Union[timedelta, int, None] = None,
        max_messages: Optional[int] = None,
        is_scheduled: bool = False,
    ) -> None:
        self.signing_key = signing_key
        self.sender_key = sender_key
        self.room_id = room_id
        self.forwarding_chain = forwarding_chain or []
        self.ratchet_safety = ratchet_safety or RatchetSafety()
        self.received_at = received_at or datetime.utcnow()
        if isinstance(max_age, int):
            max_age = timedelta(milliseconds=max_age)
        self.max_age = max_age
        self.max_messages = max_messages
        self.is_scheduled = is_scheduled
        super().__init__(session_key)

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    @classmethod
    def from_pickle(
        cls,
        pickle: bytes,
        passphrase: str,
        signing_key: SigningKey,
        sender_key: IdentityKey,
        room_id: RoomID,
        forwarding_chain: Optional[List[IdentityKey]] = None,
        ratchet_safety: Optional[RatchetSafety] = None,
        received_at: Optional[datetime] = None,
        max_age: Optional[timedelta] = None,
        max_messages: Optional[int] = None,
        is_scheduled: bool = False,
    ) -> "InboundGroupSession":
        session = super().from_pickle(pickle, passphrase)
        session.signing_key = signing_key
        session.sender_key = sender_key
        session.room_id = room_id
        session.forwarding_chain = forwarding_chain or []
        session.ratchet_safety = ratchet_safety or RatchetSafety()
        session.received_at = received_at
        session.max_age = max_age
        session.max_messages = max_messages
        session.is_scheduled = is_scheduled
        return session

    @classmethod
    def import_session(
        cls,
        session_key: str,
        signing_key: SigningKey,
        sender_key: IdentityKey,
        room_id: RoomID,
        forwarding_chain: Optional[List[str]] = None,
        ratchet_safety: Optional[RatchetSafety] = None,
        received_at: Optional[datetime] = None,
        max_age: Union[timedelta, int, None] = None,
        max_messages: Optional[int] = None,
        is_scheduled: bool = False,
    ) -> "InboundGroupSession":
        session = super().import_session(session_key)
        session.signing_key = signing_key
        session.sender_key = sender_key
        session.room_id = room_id
        session.forwarding_chain = forwarding_chain or []
        session.ratchet_safety = ratchet_safety or RatchetSafety()
        session.received_at = received_at or datetime.utcnow()
        if isinstance(max_age, int):
            max_age = timedelta(milliseconds=max_age)
        session.max_age = max_age
        session.max_messages = max_messages
        session.is_scheduled = is_scheduled
        return session

    def ratchet_to(self, index: int) -> "InboundGroupSession":
        exported = self.export_session(index)
        return self.import_session(
            exported,
            signing_key=self.signing_key,
            sender_key=self.sender_key,
            room_id=self.room_id,
            forwarding_chain=self.forwarding_chain,
            ratchet_safety=self.ratchet_safety,
            received_at=self.received_at,
            max_age=self.max_age,
            max_messages=self.max_messages,
            is_scheduled=self.is_scheduled,
        )


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

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    @property
    def expired(self):
        return (
            self.message_count >= self.max_messages
            or datetime.now() - self.creation_time >= self.max_age
        )

    def encrypt(self, plaintext):
        if not self.shared:
            raise EncryptionError("Group session has not been shared")

        if self.expired:
            raise EncryptionError("Group session has expired")

        self.message_count += 1
        self.use_time = datetime.now()
        return super().encrypt(plaintext)

    @classmethod
    def from_pickle(
        cls,
        pickle: bytes,
        passphrase: str,
        max_age: timedelta,
        max_messages: int,
        creation_time: datetime,
        use_time: datetime,
        message_count: int,
        room_id: RoomID,
        shared: bool,
    ) -> "OutboundGroupSession":
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

    @property
    def share_content(self) -> RoomKeyEventContent:
        return RoomKeyEventContent(
            algorithm=EncryptionAlgorithm.MEGOLM_V1,
            room_id=self.room_id,
            session_id=self.id,
            session_key=self.session_key,
        )
