# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict
import asyncio

from mautrix.types import (
    DecryptedOlmEvent,
    DeviceID,
    DeviceIdentity,
    EncryptedOlmEventContent,
    EncryptionKeyAlgorithm,
    EventType,
    OlmEventKeys,
    ToDeviceEventContent,
    UserID,
)

from .base import BaseOlmMachine, verify_signature_json
from .sessions import Session

ClaimKeysList = Dict[UserID, Dict[DeviceID, DeviceIdentity]]


class OlmEncryptionMachine(BaseOlmMachine):
    _claim_keys_lock: asyncio.Lock
    _olm_lock: asyncio.Lock

    def __init__(self):
        self._claim_keys_lock = asyncio.Lock()
        self._olm_lock = asyncio.Lock()

    async def _encrypt_olm_event(
        self, session: Session, recipient: DeviceIdentity, event_type: EventType, content: Any
    ) -> EncryptedOlmEventContent:
        evt = DecryptedOlmEvent(
            sender=self.client.mxid,
            sender_device=self.client.device_id,
            keys=OlmEventKeys(ed25519=self.account.signing_key),
            recipient=recipient.user_id,
            recipient_keys=OlmEventKeys(ed25519=recipient.signing_key),
            type=event_type,
            content=content,
        )
        ciphertext = session.encrypt(evt.json())
        await self.crypto_store.update_session(recipient.identity_key, session)
        return EncryptedOlmEventContent(
            ciphertext={recipient.identity_key: ciphertext}, sender_key=self.account.identity_key
        )

    async def _create_outbound_sessions(
        self, users: ClaimKeysList, _force_recreate_session: bool = False
    ) -> None:
        async with self._claim_keys_lock:
            return await self._create_outbound_sessions_locked(users, _force_recreate_session)

    async def _create_outbound_sessions_locked(
        self, users: ClaimKeysList, _force_recreate_session: bool = False
    ) -> None:
        request: Dict[UserID, Dict[DeviceID, EncryptionKeyAlgorithm]] = {}
        expected_devices = set()
        for user_id, devices in users.items():
            request[user_id] = {}
            for device_id, identity in devices.items():
                if _force_recreate_session or not await self.crypto_store.has_session(
                    identity.identity_key
                ):
                    request[user_id][device_id] = EncryptionKeyAlgorithm.SIGNED_CURVE25519
                    expected_devices.add((user_id, device_id))
            if not request[user_id]:
                del request[user_id]
        if not request:
            return
        request_device_count = len(expected_devices)
        keys = await self.client.claim_keys(request)
        for server, info in (keys.failures or {}).items():
            self.log.warning(f"Key claim failure for {server}: {info}")
        for user_id, devices in keys.one_time_keys.items():
            for device_id, one_time_keys in devices.items():
                expected_devices.discard((user_id, device_id))
                key_id, one_time_key_data = one_time_keys.popitem()
                one_time_key = one_time_key_data["key"]
                identity = users[user_id][device_id]
                if not verify_signature_json(
                    one_time_key_data, user_id, device_id, identity.signing_key
                ):
                    self.log.warning(f"Invalid signature for {device_id} of {user_id}")
                else:
                    session = self.account.new_outbound_session(
                        identity.identity_key, one_time_key
                    )
                    await self.crypto_store.add_session(identity.identity_key, session)
                    self.log.debug(
                        f"Created new Olm session with {user_id}/{device_id} "
                        f"(OTK ID: {key_id})"
                    )
        if expected_devices:
            if request_device_count == 1:
                raise Exception(
                    "Key claim response didn't contain key "
                    f"for queried device {expected_devices.pop()}"
                )
            else:
                self.log.warning(
                    "Key claim response didn't contain keys for %d out of %d expected devices: %s",
                    len(expected_devices),
                    request_device_count,
                    expected_devices,
                )

    async def send_encrypted_to_device(
        self,
        device: DeviceIdentity,
        event_type: EventType,
        content: ToDeviceEventContent,
        _force_recreate_session: bool = False,
    ) -> None:
        await self._create_outbound_sessions(
            {device.user_id: {device.device_id: device}},
            _force_recreate_session=_force_recreate_session,
        )
        session = await self.crypto_store.get_latest_session(device.identity_key)
        async with self._olm_lock:
            encrypted_content = await self._encrypt_olm_event(session, device, event_type, content)
            await self.client.send_to_one_device(
                EventType.TO_DEVICE_ENCRYPTED, device.user_id, device.device_id, encrypted_content
            )
