# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import json

import olm

from mautrix.types import EncryptedMegolmEventContent, EncryptionAlgorithm, Event, EncryptedEvent
from mautrix.errors import (DecryptionError, SessionNotFound, DuplicateMessageIndex,
                            VerificationError, DecryptedPayloadError, MismatchingRoomError)

from .types import TrustState
from .base import BaseOlmMachine


class MegolmDecryptionMachine(BaseOlmMachine):
    async def decrypt_megolm_event(self, evt: EncryptedEvent) -> Event:
        """
        Decrypt an event that was encrypted using Megolm.

        Args:
            evt: The whole encrypted event.

        Returns:
            The decrypted event, including some unencrypted metadata from the input event.

        Raises:
            DecryptionError: If decryption failed.
        """
        if not isinstance(evt.content, EncryptedMegolmEventContent):
            raise DecryptionError("Unsupported event content class")
        elif evt.content.algorithm != EncryptionAlgorithm.MEGOLM_V1:
            raise DecryptionError("Unsupported event encryption algorithm")
        session = await self.crypto_store.get_group_session(evt.room_id, evt.content.sender_key,
                                                            evt.content.session_id)
        if session is None:
            # TODO check if olm session is wedged
            raise SessionNotFound(evt.content.session_id, evt.content.sender_key)
        try:
            plaintext, index = session.decrypt(evt.content.ciphertext)
        except olm.OlmGroupSessionError as e:
            raise DecryptionError("Failed to decrypt megolm event") from e
        if not await self.crypto_store.validate_message_index(evt.content.sender_key,
                                                              evt.content.session_id,
                                                              evt.event_id, index, evt.timestamp):
            raise DuplicateMessageIndex()

        verified = False
        if ((evt.content.device_id == self.client.device_id
             and session.signing_key == self.account.signing_key
             and evt.content.sender_key == self.account.identity_key)):
            verified = True
        else:
            device = await self.crypto_store.get_device(evt.sender, evt.content.device_id)
            if device and device.trust == TrustState.VERIFIED and not session.forwarding_chain:
                if ((device.signing_key != session.signing_key
                     or device.identity_key != evt.content.sender_key)):
                    raise VerificationError()
                verified = True
            # else: TODO query device keys?

        try:
            data = json.loads(plaintext)
            room_id = data["room_id"]
            event_type = data["type"]
            content = data["content"]
        except json.JSONDecodeError as e:
            raise DecryptedPayloadError("Failed to parse megolm payload") from e
        except KeyError as e:
            raise DecryptedPayloadError("Megolm payload is missing fields") from e

        if room_id != evt.room_id:
            raise MismatchingRoomError()

        result = Event.deserialize({
            "room_id": evt.room_id,
            "event_id": evt.event_id,
            "sender": evt.sender,
            "origin_server_ts": evt.timestamp,
            "type": event_type,
            "content": content,
        })
        result.unsigned = evt.unsigned
        if evt.content.relates_to:
            if hasattr(result.content, "relates_to"):
                if not result.content.relates_to:
                    result.content.relates_to = evt.content.relates_to
            elif "m.relates_to" not in result.content:
                result.content["m.relates_to"] = evt.content.relates_to.serialize()
        result.type = result.type.with_class(evt.type.t_class)
        result["mautrix"] = {
            "verified": verified,
        }
        return result
