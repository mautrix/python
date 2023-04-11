# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import NamedTuple
from abc import ABC, abstractmethod

from mautrix.types import (
    CrossSigner,
    CrossSigningUsage,
    DeviceID,
    DeviceIdentity,
    EventID,
    IdentityKey,
    RoomEncryptionStateEventContent,
    RoomID,
    SessionID,
    SigningKey,
    TOFUSigningKey,
    UserID,
)

from ..account import OlmAccount
from ..sessions import InboundGroupSession, OutboundGroupSession, Session


class StateStore(ABC):
    @abstractmethod
    async def is_encrypted(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    async def get_encryption_info(self, room_id: RoomID) -> RoomEncryptionStateEventContent | None:
        pass

    @abstractmethod
    async def find_shared_rooms(self, user_id: UserID) -> list[RoomID]:
        pass


class CryptoStore(ABC):
    """
    CryptoStore is used by :class:`OlmMachine` to store Olm and Megolm sessions, user device lists
    and message indices.
    """

    account_id: str
    """The unique identifier for the account that is stored in this CryptoStore."""
    pickle_key: str
    """The pickle key to use when pickling Olm objects."""

    @abstractmethod
    async def get_device_id(self) -> DeviceID | None:
        """
        Get the device ID corresponding to this account_id

        Returns:
            The device ID in the store.
        """

    @abstractmethod
    async def put_device_id(self, device_id: DeviceID) -> None:
        """
        Store a device ID.

        Args:
            device_id: The device ID to store.
        """

    async def open(self) -> None:
        """
        Open the store. If the store doesn't require opening any resources beforehand or only opens
        when flushing, this can be a no-op
        """

    async def close(self) -> None:
        """
        Close the store when it will no longer be used. The default implementation will simply call
        .flush(). If the store doesn't keep any persistent resources, the default implementation is
        sufficient.
        """
        await self.flush()

    async def flush(self) -> None:
        """Flush the store. If all the methods persist data immediately, this can be a no-op."""

    @abstractmethod
    async def delete(self) -> None:
        """Delete the data in the store."""

    @abstractmethod
    async def put_account(self, account: OlmAccount) -> None:
        """Insert or update the OlmAccount in the store."""

    @abstractmethod
    async def get_account(self) -> OlmAccount | None:
        """Get the OlmAccount that was previously inserted with :meth:`put_account`.
        If no account has been inserted, this must return ``None``."""

    @abstractmethod
    async def has_session(self, key: IdentityKey) -> bool:
        """
        Check whether or not the store has a session for a specific device.

        Args:
            key: The curve25519 identity key of the device to check.

        Returns:
            ``True`` if the session has at least one Olm session for the given identity key,
            ``False`` otherwise.
        """

    @abstractmethod
    async def get_sessions(self, key: IdentityKey) -> list[Session]:
        """
        Get all Olm sessions in the store for the specific device.

        Args:
            key: The curve25519 identity key of the device whose sessions to get.

        Returns:
            A list of Olm sessions for the given identity key.
            If the store contains no sessions, an empty list.
        """

    @abstractmethod
    async def get_latest_session(self, key: IdentityKey) -> Session | None:
        """
        Get the Olm session with the highest session ID (lexiographically sorting) for a specific
        device. It's usually safe to return the most recently added session if sorting by session
        ID is too difficult.

        Args:
            key: The curve25519 identity key of the device whose session to get.

        Returns:
            The most recent session for the given device.
            If the store contains no sessions, ``None``.
        """

    @abstractmethod
    async def add_session(self, key: IdentityKey, session: Session) -> None:
        """
        Insert an Olm session into the store.

        Args:
            key: The curve25519 identity key of the device with whom this session was made.
            session: The session itself.
        """

    @abstractmethod
    async def update_session(self, key: IdentityKey, session: Session) -> None:
        """
        Update a session in the store. Implementations may assume that the given session was
        previously either inserted with :meth:`add_session` or fetched with either
        :meth:`get_sessions` or :meth:`get_latest_session`.

        Args:
            key: The curve25519 identity key of the device with whom this session was made.
            session: The session itself.
        """

    @abstractmethod
    async def put_group_session(
        self,
        room_id: RoomID,
        sender_key: IdentityKey,
        session_id: SessionID,
        session: InboundGroupSession,
    ) -> None:
        """
        Insert an inbound Megolm session into the store.

        Args:
            room_id: The room ID for which this session was made.
            sender_key: The curve25519 identity key of the user who made this session.
            session_id: The unique identifier for this session.
            session: The session itself.
        """

    @abstractmethod
    async def get_group_session(
        self, room_id: RoomID, session_id: SessionID
    ) -> InboundGroupSession | None:
        """
        Get an inbound Megolm group session that was previously inserted with
        :meth:`put_group_session`.

        Args:
            room_id: The room ID for which the session was made.
            session_id: The unique identifier of the session.

        Returns:
            The :class:`InboundGroupSession` object, or ``None`` if not found.
        """

    @abstractmethod
    async def redact_group_session(
        self, room_id: RoomID, session_id: SessionID, reason: str
    ) -> None:
        """
        Remove the keys for a specific Megolm group session.

        Args:
            room_id: The room where the session is.
            session_id: The session ID to remove.
            reason: The reason the session is being removed.
        """

    @abstractmethod
    async def redact_group_sessions(
        self, room_id: RoomID | None, sender_key: IdentityKey | None, reason: str
    ) -> list[SessionID]:
        """
        Remove the keys for multiple Megolm group sessions,
        based on the room ID and/or sender device.

        Args:
            room_id: The room ID to delete keys from.
            sender_key: The Olm identity key of the device to delete keys from.
            reason: The reason why the keys are being deleted.

        Returns:
            The list of session IDs that were deleted.
        """

    @abstractmethod
    async def redact_expired_group_sessions(self) -> list[SessionID]:
        """
        Remove all Megolm group sessions where at least twice the maximum age has passed since
        receiving the keys.

        Returns:
            The list of session IDs that were deleted.
        """

    @abstractmethod
    async def has_group_session(self, room_id: RoomID, session_id: SessionID) -> bool:
        """
        Check whether or not a specific inbound Megolm session is in the store. This is used before
        importing forwarded keys.

        Args:
            room_id: The room ID for which the session was made.
            session_id: The unique identifier of the session.

        Returns:
            ``True`` if the store has a session with the given ID, ``False`` otherwise.
        """

    @abstractmethod
    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None:
        """
        Insert an outbound Megolm session into the store.

        The store should index inserted sessions by the room_id field of the session to support
        getting and removing sessions. There will only be one outbound session per room ID at a
        time.

        Args:
            session: The session itself.
        """

    @abstractmethod
    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None:
        """
        Update an outbound Megolm session in the store. Implementations may assume that the given
        session was previously either inserted with :meth:`add_outbound_group_session` or fetched
        with :meth:`get_outbound_group_session`.

        Args:
            session: The session itself.
        """

    @abstractmethod
    async def get_outbound_group_session(self, room_id: RoomID) -> OutboundGroupSession | None:
        """
        Get the stored outbound Megolm session from the store.

        Args:
            room_id: The room whose session to get.

        Returns:
            The :class:`OutboundGroupSession` object, or ``None`` if not found.
        """

    @abstractmethod
    async def remove_outbound_group_session(self, room_id: RoomID) -> None:
        """
        Remove the stored outbound Megolm session for a specific room.

        This is used when a membership change is received in a specific room.

        Args:
            room_id: The room whose session to remove.
        """

    @abstractmethod
    async def remove_outbound_group_sessions(self, rooms: list[RoomID]) -> None:
        """
        Remove the stored outbound Megolm session for multiple rooms.

        This is used when the device list of a user changes.

        Args:
            rooms: The list of rooms whose sessions to remove.
        """

    @abstractmethod
    async def validate_message_index(
        self,
        sender_key: IdentityKey,
        session_id: SessionID,
        event_id: EventID,
        index: int,
        timestamp: int,
    ) -> bool:
        """
        Validate that a specific message isn't a replay attack.

        Implementations should store a map from ``(sender_key, session_id, index)`` to
        ``(event_id, timestamp)``, then use that map to check whether or not the message
        index is valid:

        * If the map key doesn't exist, the given values should be stored and the message is valid.
        * If the map key exists and the stored values match the given values, the message is valid.
        * If the map key exists, but the stored values do not match the given values, the message
          is not valid.

        Args:
            sender_key: The curve25519 identity key of the user who sent the message.
            session_id: The Megolm session ID for the session with which the message was encrypted.
            event_id: The event ID of the message.
            index: The Megolm message index of the message.
            timestamp: The timestamp of the message.

        Returns:
            ``True`` if the message is valid, ``False`` if not.
        """

    @abstractmethod
    async def get_devices(self, user_id: UserID) -> dict[DeviceID, DeviceIdentity] | None:
        """
        Get all devices for a given user.

        Args:
            user_id: The ID of the user whose devices to get.

        Returns:
            If there has been a previous call to :meth:`put_devices` with the same user ID (even
            with an empty dict), a dict from device ID to :class:`DeviceIdentity` object.
            Otherwise, ``None``.
        """

    @abstractmethod
    async def get_device(self, user_id: UserID, device_id: DeviceID) -> DeviceIdentity | None:
        """
        Get a specific device identity.

        Args:
            user_id: The ID of the user whose device to get.
            device_id: The ID of the device to get.

        Returns:
            The :class:`DeviceIdentity` object, or ``None`` if not found.
        """

    @abstractmethod
    async def find_device_by_key(
        self, user_id: UserID, identity_key: IdentityKey
    ) -> DeviceIdentity | None:
        """
        Find a specific device identity based on the identity key.

        Args:
            user_id: The ID of the user whose device to get.
            identity_key: The identity key of the device to get.

        Returns:
            The :class:`DeviceIdentity` object, or ``None`` if not found.
        """

    @abstractmethod
    async def put_devices(self, user_id: UserID, devices: dict[DeviceID, DeviceIdentity]) -> None:
        """
        Replace the stored device list for a specific user.

        Args:
            user_id: The ID of the user whose device list to update.
            devices: A dict from device ID to :class:`DeviceIdentity` object. The dict may be empty.
        """

    @abstractmethod
    async def filter_tracked_users(self, users: list[UserID]) -> list[UserID]:
        """
        Filter a list of user IDs to only include users whose device lists are being tracked.

        Args:
            users: The list of user IDs to filter.

        Returns:
            A filtered version of the input list that only includes users who have had a previous
            call to :meth:`put_devices` (even if the call was with an empty dict).
        """

    @abstractmethod
    async def put_cross_signing_key(
        self, user_id: UserID, usage: CrossSigningUsage, key: SigningKey
    ) -> None:
        """
        Store a single cross-signing key.

        Args:
            user_id: The user whose cross-signing key is being stored.
            usage: The type of key being stored.
            key: The key itself.
        """

    @abstractmethod
    async def get_cross_signing_keys(
        self, user_id: UserID
    ) -> dict[CrossSigningUsage, TOFUSigningKey]:
        """
        Retrieve stored cross-signing keys for a specific user.

        Args:
            user_id: The user whose cross-signing keys to get.

        Returns:
            A map from the type of key to a tuple containing the current key and the key that was
            seen first. If the keys are different, it should be treated as a local TOFU violation.
        """

    @abstractmethod
    async def put_signature(
        self, target: CrossSigner, signer: CrossSigner, signature: str
    ) -> None:
        """
        Store a signature for a given key from a given key.

        Args:
            target: The user ID and key being signed.
            signer: The user ID and key who are doing the signing.
            signature: The signature.
        """

    @abstractmethod
    async def is_key_signed_by(self, target: CrossSigner, signer: CrossSigner) -> bool:
        """
        Check if a given key is signed by the given signer.

        Args:
            target: The key to check.
            signer: The signer who is expected to have signed the key.

        Returns:
            ``True`` if the database contains a signature for the key, ``False`` otherwise.
        """

    @abstractmethod
    async def drop_signatures_by_key(self, signer: CrossSigner) -> int:
        """
        Delete signatures made by the given key.

        Args:
            signer: The key whose signatures to delete.

        Returns:
            The number of signatures deleted.
        """
