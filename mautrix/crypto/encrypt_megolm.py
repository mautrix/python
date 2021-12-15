# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, List, Tuple, Union
from collections import defaultdict
from datetime import timedelta
import asyncio
import json
import time

from mautrix.errors import EncryptionError, SessionShareError
from mautrix.types import (
    DeviceID,
    EncryptedMegolmEventContent,
    EncryptionAlgorithm,
    EventType,
    IdentityKey,
    RelatesTo,
    RoomID,
    RoomKeyWithheldCode,
    RoomKeyWithheldEventContent,
    Serializable,
    SessionID,
    SigningKey,
    UserID,
)

from .device_lists import DeviceListMachine
from .encrypt_olm import OlmEncryptionMachine
from .sessions import InboundGroupSession, OutboundGroupSession, Session
from .types import DeviceIdentity, TrustState


class Sentinel:
    pass


already_shared = Sentinel()
key_missing = Sentinel()

DeviceSessionWrapper = Tuple[Session, DeviceIdentity]
DeviceMap = Dict[UserID, Dict[DeviceID, DeviceSessionWrapper]]
SessionEncryptResult = Union[
    type(already_shared),  # already shared
    DeviceSessionWrapper,  # share successful
    RoomKeyWithheldEventContent,  # won't share
    type(key_missing),  # missing device
]


class MegolmEncryptionMachine(OlmEncryptionMachine, DeviceListMachine):
    _megolm_locks: Dict[RoomID, asyncio.Lock]
    _sharing_group_session: Dict[RoomID, asyncio.Event]

    def __init__(self) -> None:
        super().__init__()
        self._megolm_locks = defaultdict(lambda: asyncio.Lock())
        self._sharing_group_session = {}

    async def encrypt_megolm_event(
        self, room_id: RoomID, event_type: EventType, content: Any
    ) -> EncryptedMegolmEventContent:
        """
        Encrypt an event for a specific room using Megolm.

        Args:
            room_id: The room to encrypt the message for.
            event_type: The event type.
            content: The event content. Using the content structs in the mautrix.types
                module is recommended.

        Returns:
            The encrypted event content.

        Raises:
            EncryptionError: If a group session has not been shared.
                Use :meth:`share_group_session` to share a group session if this error is raised.
        """
        # The crypto store is async, so we need to make sure only one thing is writing at a time.
        async with self._megolm_locks[room_id]:
            return await self._encrypt_megolm_event(room_id, event_type, content)

    async def _encrypt_megolm_event(
        self, room_id: RoomID, event_type: EventType, content: Any
    ) -> EncryptedMegolmEventContent:
        self.log.debug(f"Encrypting event of type {event_type} for {room_id}")
        session = await self.crypto_store.get_outbound_group_session(room_id)
        if not session:
            raise EncryptionError("No group session created")
        ciphertext = session.encrypt(
            json.dumps(
                {
                    "room_id": room_id,
                    "type": event_type.serialize(),
                    "content": content.serialize()
                    if isinstance(content, Serializable)
                    else content,
                }
            )
        )
        try:
            relates_to = content.relates_to
        except AttributeError:
            try:
                relates_to = RelatesTo.deserialize(content["m.relates_to"])
            except KeyError:
                relates_to = None
        await self.crypto_store.update_outbound_group_session(session)
        return EncryptedMegolmEventContent(
            sender_key=self.account.identity_key,
            device_id=self.client.device_id,
            ciphertext=ciphertext,
            session_id=SessionID(session.id),
            relates_to=relates_to,
        )

    def is_sharing_group_session(self, room_id: RoomID) -> bool:
        """
        Check if there's a group session being shared for a specific room

        Args:
            room_id: The room ID to check.

        Returns:
            True if a group session share is in progress, False if not
        """
        return room_id in self._sharing_group_session

    async def wait_group_session_share(self, room_id: RoomID) -> None:
        """
        Wait for a group session to be shared.

        Args:
            room_id: The room ID to wait for.
        """
        try:
            event = self._sharing_group_session[room_id]
            await event.wait()
        except KeyError:
            pass

    async def share_group_session(self, room_id: RoomID, users: List[UserID]) -> None:
        """
        Create a Megolm session for a specific room and share it with the given list of users.

        Note that you must not call this method again before the previous share has finished.
        You should either lock calls yourself, or use :meth:`wait_group_session_share` to use
        built-in locking capabilities.

        Args:
            room_id: The room to create the session for.
            users: The list of users to share the session with.

        Raises:
            SessionShareError: If something went wrong while sharing the session.
        """
        if room_id in self._sharing_group_session:
            raise SessionShareError("Already sharing group session for that room")
        self._sharing_group_session[room_id] = asyncio.Event()
        try:
            await self._share_group_session(room_id, users)
        finally:
            self._sharing_group_session.pop(room_id).set()

    async def _share_group_session(self, room_id: RoomID, users: List[UserID]) -> None:
        session = await self.crypto_store.get_outbound_group_session(room_id)
        if session and session.shared and not session.expired:
            raise SessionShareError("Group session has already been shared")
        if not session or session.expired:
            session = await self._new_outbound_group_session(room_id)
        self.log.debug(f"Sharing group session {session.id} for room {room_id} with {users}")

        encryption_info = await self.state_store.get_encryption_info(room_id)
        if encryption_info:
            if encryption_info.algorithm != EncryptionAlgorithm.MEGOLM_V1:
                raise SessionShareError("Room encryption algorithm is not supported")
            session.max_messages = encryption_info.rotation_period_msgs or session.max_messages
            session.max_age = (
                timedelta(milliseconds=encryption_info.rotation_period_ms)
                if encryption_info.rotation_period_ms
                else session.max_age
            )
            self.log.debug(
                "Got stored encryption state event and configured session to rotate "
                f"after {session.max_messages} messages or {session.max_age}"
            )

        olm_sessions: DeviceMap = defaultdict(lambda: {})
        withhold_key_msgs = defaultdict(lambda: {})
        missing_sessions: Dict[UserID, Dict[DeviceID, DeviceIdentity]] = defaultdict(lambda: {})
        fetch_keys = []

        for user_id in users:
            devices = await self.crypto_store.get_devices(user_id)
            if devices is None:
                self.log.debug(
                    f"get_devices returned nil for {user_id}, will fetch keys and retry"
                )
                fetch_keys.append(user_id)
            elif len(devices) == 0:
                self.log.debug(f"{user_id} has no devices, skipping")
            else:
                self.log.debug(f"Trying to encrypt group session {session.id} for {user_id}")
                for device_id, device in devices.items():
                    result = await self._find_olm_sessions(session, user_id, device_id, device)
                    if isinstance(result, RoomKeyWithheldEventContent):
                        withhold_key_msgs[user_id][device_id] = result
                    elif result == key_missing:
                        missing_sessions[user_id][device_id] = device
                    elif isinstance(result, tuple):
                        olm_sessions[user_id][device_id] = result

        if fetch_keys:
            self.log.debug(f"Fetching missing keys for {fetch_keys}")
            fetched_keys = await self._fetch_keys(users, include_untracked=True)
            for user_id, devices in fetched_keys.items():
                missing_sessions[user_id] = devices

        if missing_sessions:
            self.log.debug(f"Creating missing outbound sessions {missing_sessions}")
            await self._create_outbound_sessions(missing_sessions)

        for user_id, devices in missing_sessions.items():
            for device_id, device in devices.items():
                result = await self._find_olm_sessions(session, user_id, device_id, device)
                if isinstance(result, RoomKeyWithheldEventContent):
                    withhold_key_msgs[user_id][device_id] = result
                elif isinstance(result, tuple):
                    olm_sessions[user_id][device_id] = result
                # We don't care about missing keys at this point

        if len(olm_sessions) > 0:
            async with self._olm_lock:
                await self._encrypt_and_share_group_session(session, olm_sessions)
        if len(withhold_key_msgs) > 0:
            event_count = sum(len(map) for map in withhold_key_msgs.values())
            self.log.debug(
                f"Sending {event_count} to-device events to report {session.id} is withheld"
            )
            await self.client.send_to_device(EventType.ROOM_KEY_WITHHELD, withhold_key_msgs)
            await self.client.send_to_device(
                EventType.ORG_MATRIX_ROOM_KEY_WITHHELD, withhold_key_msgs
            )
        self.log.info(f"Group session {session.id} for {room_id} successfully shared")
        session.shared = True
        await self.crypto_store.add_outbound_group_session(session)

    async def _new_outbound_group_session(self, room_id: RoomID) -> OutboundGroupSession:
        session = OutboundGroupSession(room_id)
        await self._create_group_session(
            self.account.identity_key,
            self.account.signing_key,
            room_id,
            SessionID(session.id),
            session.session_key,
        )
        return session

    async def _encrypt_and_share_group_session(
        self, session: OutboundGroupSession, olm_sessions: DeviceMap
    ):
        msgs = defaultdict(lambda: {})
        count = 0
        for user_id, devices in olm_sessions.items():
            count += len(devices)
            for device_id, (olm_session, device_identity) in devices.items():
                msgs[user_id][device_id] = await self._encrypt_olm_event(
                    olm_session, device_identity, EventType.ROOM_KEY, session.share_content
                )
        self.log.debug(
            f"Sending to-device events to {count} devices of {len(msgs)} users "
            f"to share {session.id}"
        )
        await self.client.send_to_device(EventType.TO_DEVICE_ENCRYPTED, msgs)

    async def _create_group_session(
        self,
        sender_key: IdentityKey,
        signing_key: SigningKey,
        room_id: RoomID,
        session_id: SessionID,
        session_key: str,
    ) -> None:
        start = time.monotonic()
        session = InboundGroupSession(
            session_key=session_key,
            signing_key=signing_key,
            sender_key=sender_key,
            room_id=room_id,
        )
        olm_duration = time.monotonic() - start
        if olm_duration > 5:
            self.log.warning(f"Creating inbound group session took {olm_duration:.3f} seconds!")
        if session_id != session.id:
            self.log.warning(f"Mismatching session IDs: expected {session_id}, got {session.id}")
            session_id = session.id
        await self.crypto_store.put_group_session(room_id, sender_key, session_id, session)
        self._mark_session_received(session_id)
        self.log.debug(f"Created inbound group session {room_id}/{sender_key}/{session_id}")

    async def _find_olm_sessions(
        self,
        session: OutboundGroupSession,
        user_id: UserID,
        device_id: DeviceID,
        device: DeviceIdentity,
    ) -> SessionEncryptResult:
        key = (user_id, device_id)
        if key in session.users_ignored or key in session.users_shared_with:
            return already_shared
        elif user_id == self.client.mxid and device_id == self.client.device_id:
            session.users_ignored.add(key)
            return already_shared

        if device.trust == TrustState.BLACKLISTED:
            self.log.debug(
                f"Not encrypting group session {session.id} for {device_id} "
                f"of {user_id}: device is blacklisted"
            )
            session.users_ignored.add(key)
            return RoomKeyWithheldEventContent(
                room_id=session.room_id,
                algorithm=EncryptionAlgorithm.MEGOLM_V1,
                session_id=SessionID(session.id),
                sender_key=self.account.identity_key,
                code=RoomKeyWithheldCode.BLACKLISTED,
                reason="Device is blacklisted",
            )
        elif not self.allow_unverified_devices and device.trust == TrustState.UNSET:
            self.log.debug(
                f"Not encrypting group session {session.id} for {device_id} "
                f"of {user_id}: device is not verified"
            )
            session.users_ignored.add(key)
            return RoomKeyWithheldEventContent(
                room_id=session.room_id,
                algorithm=EncryptionAlgorithm.MEGOLM_V1,
                session_id=SessionID(session.id),
                sender_key=self.account.identity_key,
                code=RoomKeyWithheldCode.UNVERIFIED,
                reason="This device does not encrypt messages for unverified devices",
            )
        device_session = await self.crypto_store.get_latest_session(device.identity_key)
        if not device_session:
            return key_missing
        session.users_shared_with.add(key)
        return device_session, device
