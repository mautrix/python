# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Dict, Optional

from mautrix.types import UserID, SyncToken, DeviceID, DeviceKeys
from mautrix.errors import DeviceValidationError

from .base import BaseOlmMachine, verify_signature_json
from .types import DeviceIdentity, TrustState


class DeviceListMachine(BaseOlmMachine):
    async def _fetch_keys(self, users: List[UserID], since: SyncToken = "",
                          include_untracked: bool = False
                          ) -> Dict[UserID, Dict[DeviceID, DeviceIdentity]]:
        if not include_untracked:
            users = await self.crypto_store.filter_tracked_users(users)
        if len(users) == 0:
            return {}
        users = set(users)

        self.log.trace(f"Querying keys for {users}")
        keys = await self.client.query_keys(users, token=since)

        for server, err in keys.failures.items():
            self.log.warning(f"Query keys failure for {server}: {err}")

        data = {}
        for user_id, devices in keys.device_keys.items():
            users.remove(user_id)

            new_devices = {}
            existing_devices = (await self.crypto_store.get_devices(user_id)) or {}

            self.log.trace(f"Updating devices for {user_id}, got {len(devices)}, "
                           f"have {len(existing_devices)} in store")
            changed = False
            for device_id, keys in devices.items():
                try:
                    existing = existing_devices[device_id]
                except KeyError:
                    existing = None
                    changed = True
                self.log.trace(f"Validating device {keys} of {user_id}")
                try:
                    new_device = await self._validate_device(user_id, device_id, keys, existing)
                except DeviceValidationError as e:
                    self.log.warning(f"Failed to validate device {device_id} of {user_id}: {e}")
                else:
                    if new_device:
                        new_devices[device_id] = new_device
            self.log.debug(f"Storing new device list for {user_id} "
                           f"containing {len(new_devices)} devices")
            await self.crypto_store.put_devices(user_id, new_devices)
            data[user_id] = new_devices

            if changed or len(new_devices) != len(existing_devices):
                await self.on_devices_changed(user_id)

        for user_id in users:
            self.log.warning(f"Didn't get any keys for user {user_id}")

        return data

    async def get_or_fetch_device(self, user_id: UserID, device_id: DeviceID
                                  ) -> Optional[DeviceIdentity]:
        device = await self.crypto_store.get_device(user_id, device_id)
        if device is not None:
            return device
        devices = await self._fetch_keys([user_id], include_untracked=True)
        try:
            return devices[user_id][device_id]
        except KeyError:
            return None

    async def on_devices_changed(self, user_id: UserID) -> None:
        shared_rooms = await self.state_store.find_shared_rooms(user_id)
        self.log.debug(f"Devices of {user_id} changed, "
                       f"invalidating group session in {shared_rooms}")
        await self.crypto_store.remove_outbound_group_sessions(shared_rooms)

    @staticmethod
    async def _validate_device(user_id: UserID, device_id: DeviceID, device_keys: DeviceKeys,
                               existing: Optional[DeviceIdentity] = None) -> DeviceIdentity:
        if user_id != device_keys.user_id:
            raise DeviceValidationError("mismatching user ID in parameter and keys object")
        elif device_id != device_keys.device_id:
            raise DeviceValidationError("mismatching device ID in parameter and keys object")

        signing_key = device_keys.ed25519
        if not signing_key:
            raise DeviceValidationError("didn't find ed25519 signing key")
        identity_key = device_keys.curve25519
        if not identity_key:
            raise DeviceValidationError("didn't find curve25519 identity key")

        if existing and existing.signing_key != signing_key:
            raise DeviceValidationError("received update for device with different signing key")

        if not verify_signature_json(device_keys.serialize(), user_id, device_id, signing_key):
            raise DeviceValidationError("invalid signature on device keys")

        name = device_keys.unsigned.device_display_name or device_id

        return DeviceIdentity(user_id=user_id, device_id=device_id, identity_key=identity_key,
                              signing_key=signing_key, trust=TrustState.UNSET, name=name,
                              deleted=False)
