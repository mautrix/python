# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import asyncio
import logging

from mautrix import __optional_imports__
from mautrix.errors import DecryptionError, EncryptionError, MNotFound
from mautrix.types import (
    EncryptedEvent,
    EncryptedMegolmEventContent,
    EventContent,
    EventID,
    EventType,
    RoomID,
)
from mautrix.util.logging import TraceLogger

from . import client, dispatcher, store_updater

if __optional_imports__:
    from .. import crypto as crypt


class EncryptingAPI(store_updater.StoreUpdatingAPI):
    """
    EncryptingAPI is a wrapper around StoreUpdatingAPI that automatically encrypts messages.

    For automatic decryption, see :class:`DecryptionDispatcher`.
    """

    _crypto: crypt.OlmMachine | None
    encryption_blacklist: set[EventType] = {EventType.REACTION}
    """A set of event types which shouldn't be encrypted even in encrypted rooms."""
    crypto_log: TraceLogger = logging.getLogger("mau.client.crypto")
    """The logger to use for crypto-related things."""
    _share_session_events: dict[RoomID, asyncio.Event]

    def __init__(self, *args, crypto_log: TraceLogger | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if crypto_log:
            self.crypto_log = crypto_log
        self._crypto = None
        self._share_session_events = {}

    @property
    def crypto(self) -> crypt.OlmMachine | None:
        """The :class:`crypto.OlmMachine` to use for e2ee stuff."""
        return self._crypto

    @crypto.setter
    def crypto(self, crypto: crypt.OlmMachine) -> None:
        """
        Args:
            crypto: The olm machine to use for crypto

        Raises:
            ValueError: if :attr:`state_store` is not set.
        """
        if not self.state_store:
            raise ValueError("State store must be set to use encryption")
        self._crypto = crypto

    @property
    def crypto_enabled(self) -> bool:
        """``True`` if both the olm machine and state store are set properly."""
        return bool(self.crypto) and bool(self.state_store)

    async def encrypt(
        self, room_id: RoomID, event_type: EventType, content: EventContent
    ) -> EncryptedMegolmEventContent:
        """
        Encrypt a message for the given room. Automatically creates and shares a group session
        if necessary.

        Args:
            room_id: The room to encrypt the event to.
            event_type: The type of event.
            content: The content of the event.

        Returns:
            The content of the encrypted event.
        """
        try:
            return await self.crypto.encrypt_megolm_event(room_id, event_type, content)
        except EncryptionError:
            self.crypto_log.debug("Got EncryptionError, sharing group session and trying again")
            await self.share_group_session(room_id)
            self.crypto_log.trace(
                f"Shared group session, now trying to encrypt in {room_id} again"
            )
            return await self.crypto.encrypt_megolm_event(room_id, event_type, content)

    async def _share_session_lock(self, room_id: RoomID) -> bool:
        try:
            event = self._share_session_events[room_id]
        except KeyError:
            self._share_session_events[room_id] = asyncio.Event()
            return True
        else:
            await event.wait()
            return False

    async def share_group_session(self, room_id: RoomID) -> None:
        """
        Create and share a Megolm session for the given room.

        Args:
            room_id: The room to share the session for.
        """
        if not await self._share_session_lock(room_id):
            self.log.silly("Group session was already being shared, so didn't share new one")
            return
        try:
            if not await self.state_store.has_full_member_list(room_id):
                self.crypto_log.trace(
                    f"Don't have full member list for {room_id}, fetching from server"
                )
                members = list((await self.get_joined_members(room_id)).keys())
            else:
                self.crypto_log.trace(f"Fetching member list for {room_id} from state store")
                members = await self.state_store.get_members(room_id)
            await self.crypto.share_group_session(room_id, members)
        finally:
            self._share_session_events.pop(room_id).set()

    async def send_message_event(
        self,
        room_id: RoomID,
        event_type: EventType,
        content: EventContent,
        disable_encryption: bool = False,
        **kwargs,
    ) -> EventID:
        """
        A wrapper around :meth:`ClientAPI.send_message_event` that encrypts messages if the target
        room is encrypted.

        Args:
            room_id: The room to send the message to.
            event_type: The unencrypted event type.
            content: The unencrypted event content.
            disable_encryption: Set to ``True`` if you want to force-send an unencrypted message.
            **kwargs: Additional parameters to pass to :meth:`ClientAPI.send_message_event`.

        Returns:
            The ID of the event that was sent.
        """
        if self.crypto and event_type not in self.encryption_blacklist and not disable_encryption:
            is_encrypted = await self.state_store.is_encrypted(room_id)
            if is_encrypted is None:
                try:
                    await self.get_state_event(room_id, EventType.ROOM_ENCRYPTION)
                    is_encrypted = True
                except MNotFound:
                    is_encrypted = False
            if is_encrypted:
                content = await self.encrypt(room_id, event_type, content)
                event_type = EventType.ROOM_ENCRYPTED
        return await super().send_message_event(room_id, event_type, content, **kwargs)


class DecryptionDispatcher(dispatcher.SimpleDispatcher):
    """
    DecryptionDispatcher is a dispatcher that can be used with a :class:`client.Syncer`
    to automatically decrypt events and dispatch the unencrypted versions for event handlers.

    The easiest way to use this is with :class:`client.Client`, which automatically registers
    this dispatcher when :attr:`EncryptingAPI.crypto` is set.
    """

    event_type = EventType.ROOM_ENCRYPTED
    client: client.Client

    async def handle(self, evt: EncryptedEvent) -> None:
        try:
            self.client.crypto_log.trace(f"Decrypting {evt.event_id} in {evt.room_id}...")
            decrypted = await self.client.crypto.decrypt_megolm_event(evt)
        except DecryptionError as e:
            self.client.crypto_log.warning(f"Failed to decrypt {evt.event_id}: {e}")
            return
        self.client.crypto_log.trace(f"Decrypted {evt.event_id}: {decrypted}")
        self.client.dispatch_event(decrypted, evt.source)
