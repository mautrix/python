# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import json

import olm

from mautrix.errors import (
    DecryptedPayloadError,
    DecryptionError,
    DuplicateMessageIndex,
    MismatchingRoomError,
    SessionNotFound,
    VerificationError,
)
from mautrix.types import (
    EncryptedEvent,
    EncryptedMegolmEventContent,
    EncryptionAlgorithm,
    Event,
    SessionID,
    TrustState,
)

from .device_lists import DeviceListMachine


class MegolmDecryptionMachine(DeviceListMachine):
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
        session = await self.crypto_store.get_group_session(evt.room_id, evt.content.session_id)
        if session is None:
            # TODO check if olm session is wedged
            raise SessionNotFound(evt.content.session_id, evt.content.sender_key)
        try:
            plaintext, index = session.decrypt(evt.content.ciphertext)
        except olm.OlmGroupSessionError as e:
            raise DecryptionError("Failed to decrypt megolm event") from e
        if not await self.crypto_store.validate_message_index(
            session.sender_key, SessionID(session.id), evt.event_id, index, evt.timestamp
        ):
            raise DuplicateMessageIndex()

        forwarded_keys = False
        if (
            evt.content.device_id == self.client.device_id
            and session.signing_key == self.account.signing_key
            and session.sender_key == self.account.identity_key
            and not session.forwarding_chain
        ):
            trust_level = TrustState.VERIFIED
        else:
            device = await self.get_or_fetch_device_by_key(evt.sender, session.sender_key)
            if not session.forwarding_chain or (
                len(session.forwarding_chain) == 1
                and session.forwarding_chain[0] == session.sender_key
            ):
                if not device:
                    self.log.debug(
                        f"Couldn't resolve trust level of session {session.id}: "
                        f"sent by unknown device {evt.sender}/{session.sender_key}"
                    )
                    trust_level = TrustState.UNKNOWN_DEVICE
                elif (
                    device.signing_key != session.signing_key
                    or device.identity_key != session.sender_key
                ):
                    raise VerificationError()
                else:
                    trust_level = await self.resolve_trust(device)
            else:
                forwarded_keys = True
                last_chain_item = session.forwarding_chain[-1]
                received_from = await self.crypto_store.find_device_by_key(
                    evt.sender, last_chain_item
                )
                if received_from:
                    trust_level = await self.resolve_trust(received_from)
                else:
                    self.log.debug(
                        f"Couldn't resolve trust level of session {session.id}: "
                        f"forwarding chain ends with unknown device {last_chain_item}"
                    )
                    trust_level = TrustState.FORWARDED

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

        if evt.content.relates_to and "m.relates_to" not in content:
            content["m.relates_to"] = evt.content.relates_to.serialize()
        result = Event.deserialize(
            {
                "room_id": evt.room_id,
                "event_id": evt.event_id,
                "sender": evt.sender,
                "origin_server_ts": evt.timestamp,
                "type": event_type,
                "content": content,
            }
        )
        result.unsigned = evt.unsigned
        result.type = result.type.with_class(evt.type.t_class)
        result["mautrix"] = {
            "trust_state": trust_level,
            "forwarded_keys": forwarded_keys,
            "was_encrypted": True,
        }
        return result
