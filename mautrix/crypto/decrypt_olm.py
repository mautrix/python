# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
import asyncio

import olm

from mautrix.errors import DecryptionError, MatchingSessionDecryptionError
from mautrix.types import (
    EncryptedOlmEventContent,
    EncryptionAlgorithm,
    IdentityKey,
    OlmCiphertext,
    OlmMsgType,
    ToDeviceEvent,
    UserID,
)

from .base import BaseOlmMachine
from .sessions import Session
from .types import DecryptedOlmEvent


class OlmDecryptionMachine(BaseOlmMachine):
    async def _decrypt_olm_event(self, evt: ToDeviceEvent) -> DecryptedOlmEvent:
        if not isinstance(evt.content, EncryptedOlmEventContent):
            raise DecryptionError("unsupported event content class")
        elif evt.content.algorithm != EncryptionAlgorithm.OLM_V1:
            raise DecryptionError("unsupported event encryption algorithm")
        try:
            own_content = evt.content.ciphertext[self.account.identity_key]
        except KeyError:
            raise DecryptionError("olm event doesn't contain ciphertext for this device")

        self.log.debug(
            f"Decrypting to-device olm event from {evt.sender}/{evt.content.sender_key}"
        )
        plaintext = await self._decrypt_olm_ciphertext(
            evt.sender, evt.content.sender_key, own_content
        )

        try:
            decrypted_evt: DecryptedOlmEvent = DecryptedOlmEvent.parse_json(plaintext)
        except Exception:
            self.log.trace("Failed to parse olm event plaintext: %s", plaintext)
            raise
        if decrypted_evt.sender != evt.sender:
            raise DecryptionError("mismatched sender in olm payload")
        elif decrypted_evt.recipient != self.client.mxid:
            raise DecryptionError("mismatched recipient in olm payload")
        elif decrypted_evt.recipient_keys.ed25519 != self.account.signing_key:
            raise DecryptionError("mismatched recipient key in olm payload")
        decrypted_evt.sender_key = evt.content.sender_key
        decrypted_evt.source = evt
        self.log.debug(
            f"Successfully decrypted olm event from {evt.sender}/{decrypted_evt.sender_device} "
            f"(sender key: {decrypted_evt.sender_key} into a {decrypted_evt.type}"
        )
        return decrypted_evt

    async def _decrypt_olm_ciphertext(
        self, sender: UserID, sender_key: IdentityKey, message: OlmCiphertext
    ) -> str:
        if message.type not in (OlmMsgType.PREKEY, OlmMsgType.MESSAGE):
            raise DecryptionError("unsupported olm message type")

        try:
            plaintext = await self._try_decrypt_olm_ciphertext(sender_key, message)
        except MatchingSessionDecryptionError:
            self.log.warning(
                f"Found matching session yet decryption failed for sender {sender}"
                f" with key {sender_key}"
            )
            asyncio.create_task(self._unwedge_session(sender, sender_key))
            raise

        if not plaintext:
            if message.type != OlmMsgType.PREKEY:
                asyncio.create_task(self._unwedge_session(sender, sender_key))
                raise DecryptionError("Decryption failed for normal message")

            self.log.trace(f"Trying to create inbound session for {sender}/{sender_key}")
            try:
                session = await self._create_inbound_session(sender_key, message.body)
            except olm.OlmSessionError as e:
                asyncio.create_task(self._unwedge_session(sender, sender_key))
                raise DecryptionError("Failed to create new session from prekey message") from e
            self.log.debug(
                f"Created inbound session {session.id} for {sender} (sender key: {sender_key})"
            )

            try:
                plaintext = session.decrypt(message)
            except olm.OlmSessionError as e:
                raise DecryptionError(
                    "Failed to decrypt olm event with session created from prekey message"
                ) from e

            await self.crypto_store.update_session(sender_key, session)

        return plaintext

    async def _try_decrypt_olm_ciphertext(
        self, sender_key: IdentityKey, message: OlmCiphertext
    ) -> Optional[str]:
        sessions = await self.crypto_store.get_sessions(sender_key)
        for session in sessions:
            if message.type == OlmMsgType.PREKEY and not session.matches(message.body):
                continue

            try:
                plaintext = session.decrypt(message)
            except olm.OlmSessionError as e:
                if message.type == OlmMsgType.PREKEY:
                    raise MatchingSessionDecryptionError(
                        "decryption failed with matching session"
                    ) from e
            else:
                await self.crypto_store.update_session(sender_key, session)
                return plaintext
        return None

    async def _create_inbound_session(self, sender_key: IdentityKey, ciphertext: str) -> Session:
        session = self.account.new_inbound_session(sender_key, ciphertext)
        await self.crypto_store.put_account(self.account)
        await self.crypto_store.add_session(sender_key, session)
        return session

    async def _unwedge_session(self, sender: UserID, sender_key: IdentityKey) -> None:
        raise NotImplementedError()
