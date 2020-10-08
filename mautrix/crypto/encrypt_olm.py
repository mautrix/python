# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict
import asyncio

from mautrix.types import (EncryptedOlmEventContent, EventType, UserID, DeviceID,
                           EncryptionKeyAlgorithm, ToDeviceEventContent)

from .base import BaseOlmMachine, verify_signature_json
from .types import DeviceIdentity, DecryptedOlmEvent, OlmEventKeys
from .sessions import Session

ClaimKeysList = Dict[UserID, Dict[DeviceID, DeviceIdentity]]


class OlmEncryptionMachine(BaseOlmMachine):
    _claim_keys_lock: asyncio.Lock
    _olm_lock: asyncio.Lock

    def __init__(self):
        self._claim_keys_lock = asyncio.Lock()
        self._olm_lock = asyncio.Lock()

    async def _encrypt_olm_event(self, session: Session, recipient: DeviceIdentity,
                                 event_type: EventType, content: Any) -> EncryptedOlmEventContent:
        evt = DecryptedOlmEvent(sender=self.client.mxid, sender_device=self.client.device_id,
                                keys=OlmEventKeys(ed25519=self.account.signing_key),
                                recipient=recipient.user_id,
                                recipient_keys=OlmEventKeys(ed25519=recipient.signing_key),
                                type=event_type, content=content)
        ciphertext = session.encrypt(evt.json())
        await self.crypto_store.update_session(recipient.identity_key, session)
        return EncryptedOlmEventContent(ciphertext={recipient.identity_key: ciphertext},
                                        sender_key=self.account.identity_key)

    async def _create_outbound_sessions(self, users: ClaimKeysList) -> None:
        async with self._claim_keys_lock:
            return await self._create_outbound_sessions_locked(users)

    async def _create_outbound_sessions_locked(self, users: ClaimKeysList) -> None:
        request: Dict[UserID, Dict[DeviceID, EncryptionKeyAlgorithm]] = {}
        for user_id, devices in users.items():
            request[user_id] = {}
            for device_id, identity in devices.items():
                if not await self.crypto_store.has_session(identity.identity_key):
                    request[user_id][device_id] = EncryptionKeyAlgorithm.SIGNED_CURVE25519
            if not request[user_id]:
                del request[user_id]
        if not request:
            return
        keys = await self.client.claim_keys(request)
        for user_id, devices in keys.one_time_keys.items():
            for device_id, one_time_keys in devices.items():
                key_id, one_time_key_data = one_time_keys.popitem()
                one_time_key = one_time_key_data["key"]
                identity = users[user_id][device_id]
                if not verify_signature_json(one_time_key_data, user_id, device_id,
                                             identity.signing_key):
                    self.log.warning(f"Invalid signature for {device_id} of {user_id}")
                else:
                    session = self.account.new_outbound_session(identity.identity_key, one_time_key)
                    await self.crypto_store.add_session(identity.identity_key, session)

    async def send_encrypted_to_device(self, device: DeviceIdentity, event_type: EventType,
                                       content: ToDeviceEventContent) -> None:
        await self._create_outbound_sessions({device.user_id: {device.device_id: device}})
        session = await self.crypto_store.get_latest_session(device.identity_key)
        async with self._olm_lock:
            encrypted_content = await self._encrypt_olm_event(session, device, event_type, content)
            await self.client.send_to_one_device(EventType.TO_DEVICE_ENCRYPTED, device.user_id,
                                                 device.device_id, encrypted_content)
