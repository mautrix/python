# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.errors import DeviceValidationError
from mautrix.types import (
    CrossSigner,
    CrossSigningKeys,
    CrossSigningUsage,
    DeviceID,
    DeviceIdentity,
    DeviceKeys,
    EncryptionKeyAlgorithm,
    IdentityKey,
    KeyID,
    QueryKeysResponse,
    SigningKey,
    SyncToken,
    TrustState,
    UserID,
)

from .base import BaseOlmMachine, verify_signature_json


class DeviceListMachine(BaseOlmMachine):
    async def _fetch_keys(
        self, users: list[UserID], since: SyncToken = "", include_untracked: bool = False
    ) -> dict[UserID, dict[DeviceID, DeviceIdentity]]:
        if not include_untracked:
            users = await self.crypto_store.filter_tracked_users(users)
        if len(users) == 0:
            return {}
        users = set(users)

        self.log.trace(f"Querying keys for {users}")
        resp = await self.client.query_keys(users, token=since)
        missing_users = users.copy()

        for server, err in resp.failures.items():
            self.log.warning(f"Query keys failure for {server}: {err}")

        data = {}
        for user_id, devices in resp.device_keys.items():
            missing_users.remove(user_id)

            new_devices = {}
            existing_devices = (await self.crypto_store.get_devices(user_id)) or {}

            self.log.trace(
                f"Updating devices for {user_id}, got {len(devices)}, "
                f"have {len(existing_devices)} in store"
            )
            changed = False
            ssks = resp.self_signing_keys.get(user_id)
            ssk = ssks.first_ed25519_key if ssks else None
            for device_id, device_keys in devices.items():
                try:
                    existing = existing_devices[device_id]
                except KeyError:
                    existing = None
                    changed = True
                self.log.trace(f"Validating device {device_keys} of {user_id}")
                try:
                    new_device = await self._validate_device(
                        user_id, device_id, device_keys, existing
                    )
                except DeviceValidationError as e:
                    self.log.warning(f"Failed to validate device {device_id} of {user_id}: {e}")
                else:
                    if new_device:
                        new_devices[device_id] = new_device
                        await self._store_device_self_signatures(device_keys, ssk)
            self.log.debug(
                f"Storing new device list for {user_id} containing {len(new_devices)} devices"
            )
            await self.crypto_store.put_devices(user_id, new_devices)
            data[user_id] = new_devices

            if changed or len(new_devices) != len(existing_devices):
                await self.on_devices_changed(user_id)

        for user_id in missing_users:
            self.log.warning(f"Didn't get any devices for user {user_id}")

        for user_id in users:
            await self._store_cross_signing_keys(resp, user_id)

        return data

    async def _store_device_self_signatures(
        self, device_keys: DeviceKeys, self_signing_key: SigningKey | None
    ) -> None:
        device_desc = f"Device {device_keys.user_id}/{device_keys.device_id}"
        try:
            self_signatures = device_keys.signatures[device_keys.user_id].copy()
        except KeyError:
            self.log.warning(f"{device_desc} doesn't have any signatures from the user")
            return
        if len(device_keys.signatures) > 1:
            self.log.debug(
                f"{device_desc} has signatures from other users (%s)",
                set(device_keys.signatures.keys()) - {device_keys.user_id},
            )

        device_self_sig = self_signatures.pop(
            KeyID(EncryptionKeyAlgorithm.ED25519, device_keys.device_id)
        )
        target = CrossSigner(device_keys.user_id, device_keys.ed25519)
        # This one is already validated by _validate_device
        await self.crypto_store.put_signature(target, target, device_self_sig)

        try:
            cs_self_sig = self_signatures.pop(
                KeyID(EncryptionKeyAlgorithm.ED25519, self_signing_key)
            )
        except KeyError:
            self.log.warning(f"{device_desc} isn't cross-signed")
        else:
            is_valid_self_sig = verify_signature_json(
                device_keys.serialize(), device_keys.user_id, self_signing_key, self_signing_key
            )
            if is_valid_self_sig:
                signer = CrossSigner(device_keys.user_id, self_signing_key)
                await self.crypto_store.put_signature(target, signer, cs_self_sig)
            else:
                self.log.warning(f"{device_desc} doesn't have a valid cross-signing signature")

        if len(self_signatures) > 0:
            self.log.debug(
                f"{device_desc} has signatures from unexpected keys (%s)",
                set(self_signatures.keys()),
            )

    async def _store_cross_signing_keys(self, resp: QueryKeysResponse, user_id: UserID) -> None:
        new_keys: dict[CrossSigningUsage, CrossSigningKeys] = {}
        try:
            master = new_keys[CrossSigningUsage.MASTER] = resp.master_keys[user_id]
        except KeyError:
            self.log.debug(f"Didn't get a cross-signing master key for {user_id}")
            return
        try:
            new_keys[CrossSigningUsage.SELF] = resp.self_signing_keys[user_id]
        except KeyError:
            self.log.debug(f"Didn't get a cross-signing self-signing key for {user_id}")
            return
        try:
            new_keys[CrossSigningUsage.USER] = resp.user_signing_keys[user_id]
        except KeyError:
            pass
        current_keys = await self.crypto_store.get_cross_signing_keys(user_id)
        for usage, key in current_keys.items():
            if usage in new_keys and key.key != new_keys[usage].first_ed25519_key:
                num = await self.crypto_store.drop_signatures_by_key(CrossSigner(user_id, key.key))
                if num >= 0:
                    self.log.debug(
                        f"Dropped {num} signatures made by key {user_id}/{key.key} ({usage})"
                        " as it has been replaced"
                    )
        for usage, key in new_keys.items():
            actual_key = key.first_ed25519_key
            self.log.debug(f"Storing cross-signing key for {user_id}: {actual_key} (type {usage})")
            await self.crypto_store.put_cross_signing_key(user_id, usage, actual_key)

            if usage != CrossSigningUsage.MASTER and (
                KeyID(EncryptionKeyAlgorithm.ED25519, master.first_ed25519_key)
                not in key.signatures[user_id]
            ):
                self.log.warning(
                    f"Cross-signing key {user_id}/{actual_key}/{usage}"
                    " doesn't seem to have a signature from the master key"
                )

            for signer_user_id, signatures in key.signatures.items():
                for key_id, signature in signatures.items():
                    signing_key = SigningKey(key_id.key_id)
                    if signer_user_id == user_id:
                        try:
                            device = resp.device_keys[signer_user_id][DeviceID(key_id.key_id)]
                            signing_key = device.ed25519
                        except KeyError:
                            pass
                    if len(signing_key) != 43:
                        self.log.debug(
                            f"Cross-signing key {user_id}/{actual_key} has a signature from "
                            f"an unknown key {key_id}"
                        )
                        continue
                    signing_key_log = signing_key
                    if signing_key != key_id.key_id:
                        signing_key_log = f"{signing_key} ({key_id})"
                    self.log.debug(
                        f"Verifying cross-signing key {user_id}/{actual_key} "
                        f"with key {signer_user_id}/{signing_key_log}"
                    )
                    is_valid_sig = verify_signature_json(
                        key.serialize(), signer_user_id, key_id.key_id, signing_key
                    )
                    if is_valid_sig:
                        self.log.debug(f"Signature from {signing_key_log} for {key_id} verified")
                        await self.crypto_store.put_signature(
                            target=CrossSigner(user_id, actual_key),
                            signer=CrossSigner(signer_user_id, signing_key),
                            signature=signature,
                        )
                    else:
                        self.log.warning(f"Invalid signature from {signing_key_log} for {key_id}")

    async def get_or_fetch_device(
        self, user_id: UserID, device_id: DeviceID
    ) -> DeviceIdentity | None:
        device = await self.crypto_store.get_device(user_id, device_id)
        if device is not None:
            return device
        devices = await self._fetch_keys([user_id], include_untracked=True)
        try:
            return devices[user_id][device_id]
        except KeyError:
            return None

    async def get_or_fetch_device_by_key(
        self, user_id: UserID, identity_key: IdentityKey
    ) -> DeviceIdentity | None:
        device = await self.crypto_store.find_device_by_key(user_id, identity_key)
        if device is not None:
            return device
        devices = await self._fetch_keys([user_id], include_untracked=True)
        for device in devices.get(user_id, {}).values():
            if device.identity_key == identity_key:
                return device
        return None

    async def on_devices_changed(self, user_id: UserID) -> None:
        shared_rooms = await self.state_store.find_shared_rooms(user_id)
        self.log.debug(
            f"Devices of {user_id} changed, invalidating group session in {shared_rooms}"
        )
        await self.crypto_store.remove_outbound_group_sessions(shared_rooms)

    @staticmethod
    async def _validate_device(
        user_id: UserID,
        device_id: DeviceID,
        device_keys: DeviceKeys,
        existing: DeviceIdentity | None = None,
    ) -> DeviceIdentity:
        if user_id != device_keys.user_id:
            raise DeviceValidationError(
                f"mismatching user ID (expected {user_id}, got {device_keys.user_id})"
            )
        elif device_id != device_keys.device_id:
            raise DeviceValidationError(
                f"mismatching device ID (expected {device_id}, got {device_keys.device_id})"
            )

        signing_key = device_keys.ed25519
        if not signing_key:
            raise DeviceValidationError("didn't find ed25519 signing key")
        identity_key = device_keys.curve25519
        if not identity_key:
            raise DeviceValidationError("didn't find curve25519 identity key")

        if existing and existing.signing_key != signing_key:
            raise DeviceValidationError(
                f"received update for device with different signing key "
                f"(expected {existing.signing_key}, got {signing_key})"
            )

        if not verify_signature_json(device_keys.serialize(), user_id, device_id, signing_key):
            raise DeviceValidationError("invalid signature on device keys")

        name = device_keys.unsigned.device_display_name or device_id

        return DeviceIdentity(
            user_id=user_id,
            device_id=device_id,
            identity_key=identity_key,
            signing_key=signing_key,
            trust=TrustState.UNVERIFIED,
            name=name,
            deleted=False,
        )

    async def resolve_trust(self, device: DeviceIdentity) -> TrustState:
        try:
            return await self._try_resolve_trust(device)
        except Exception:
            self.log.exception(f"Failed to resolve trust of {device.user_id}/{device.device_id}")
            return TrustState.UNVERIFIED

    async def _try_resolve_trust(self, device: DeviceIdentity) -> TrustState:
        if device.trust in (TrustState.VERIFIED, TrustState.BLACKLISTED):
            return device.trust
        their_keys = await self.crypto_store.get_cross_signing_keys(device.user_id)
        if len(their_keys) == 0 and device.user_id not in self._cs_fetch_attempted:
            self.log.debug(f"Didn't find any cross-signing keys for {device.user_id}, fetching...")
            async with self._fetch_keys_lock:
                if device.user_id not in self._cs_fetch_attempted:
                    self._cs_fetch_attempted.add(device.user_id)
                    await self._fetch_keys([device.user_id])
            their_keys = await self.crypto_store.get_cross_signing_keys(device.user_id)
        try:
            msk = their_keys[CrossSigningUsage.MASTER]
            ssk = their_keys[CrossSigningUsage.SELF]
        except KeyError as e:
            self.log.error(f"Didn't find cross-signing key {e.args[0]} of {device.user_id}")
            return TrustState.UNVERIFIED
        ssk_signed = await self.crypto_store.is_key_signed_by(
            target=CrossSigner(device.user_id, ssk.key),
            signer=CrossSigner(device.user_id, msk.key),
        )
        if not ssk_signed:
            self.log.warning(
                f"Self-signing key of {device.user_id} is not signed by their master key"
            )
            return TrustState.UNVERIFIED
        device_signed = await self.crypto_store.is_key_signed_by(
            target=CrossSigner(device.user_id, device.signing_key),
            signer=CrossSigner(device.user_id, ssk.key),
        )
        if device_signed:
            if await self.is_user_trusted(device.user_id):
                return TrustState.CROSS_SIGNED_TRUSTED
            elif msk.key == msk.first:
                return TrustState.CROSS_SIGNED_TOFU
            return TrustState.CROSS_SIGNED_UNTRUSTED
        return TrustState.UNVERIFIED

    async def is_user_trusted(self, user_id: UserID) -> bool:
        # TODO implement once own cross-signing key stuff is ready
        return False
