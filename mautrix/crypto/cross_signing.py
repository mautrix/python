# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from ..types import (
    JSON,
    CrossSigner,
    CrossSigningKeys,
    CrossSigningUsage,
    DeviceIdentity,
    EventType,
    KeyID,
    UserID,
)
from .cross_signing_key import CrossSigningPrivateKeys, CrossSigningPublicKeys, CrossSigningSeeds
from .device_lists import DeviceListMachine
from .signature import sign_olm
from .ssss import Key as SSSSKey


class CrossSigningMachine(DeviceListMachine):
    _cross_signing_public_keys: CrossSigningPublicKeys | None
    _cross_signing_public_keys_fetched: bool
    _cross_signing_private_keys: CrossSigningPrivateKeys | None

    async def verify_with_recovery_key(self, recovery_key: str) -> None:
        if not self.account.shared:
            raise ValueError("Device keys must be shared before verifying with recovery key")
        key_id, key_data = await self.ssss.get_default_key_data()
        ssss_key = key_data.verify_recovery_key(key_id, recovery_key)
        seeds = await self._fetch_cross_signing_keys_from_ssss(ssss_key)
        self._import_cross_signing_keys(seeds)
        await self.sign_own_device(self.own_identity)

    def _import_cross_signing_keys(self, seeds: CrossSigningSeeds) -> None:
        self._cross_signing_private_keys = seeds.to_keys()
        self._cross_signing_public_keys = self._cross_signing_private_keys.public_keys

    async def generate_recovery_key(
        self, passphrase: str | None = None, seeds: CrossSigningSeeds | None = None
    ) -> str:
        if not self.account.shared:
            raise ValueError("Device keys must be shared before generating recovery key")
        seeds = seeds or CrossSigningSeeds.generate()
        ssss_key = await self.ssss.generate_and_upload_key(passphrase)
        await self._upload_cross_signing_keys_to_ssss(ssss_key, seeds)
        await self._publish_cross_signing_keys(seeds.to_keys())
        await self.ssss.set_default_key_id(ssss_key.id)
        await self.sign_own_device(self.own_identity)
        return ssss_key.recovery_key

    async def _fetch_cross_signing_keys_from_ssss(self, key: SSSSKey) -> CrossSigningSeeds:
        return CrossSigningSeeds(
            master_key=await self.ssss.get_decrypted_account_data(
                EventType.CROSS_SIGNING_MASTER, key
            ),
            user_signing_key=await self.ssss.get_decrypted_account_data(
                EventType.CROSS_SIGNING_USER_SIGNING, key
            ),
            self_signing_key=await self.ssss.get_decrypted_account_data(
                EventType.CROSS_SIGNING_SELF_SIGNING, key
            ),
        )

    async def _upload_cross_signing_keys_to_ssss(
        self, key: SSSSKey, seeds: CrossSigningSeeds
    ) -> None:
        await self.ssss.set_encrypted_account_data(
            EventType.CROSS_SIGNING_MASTER, seeds.master_key, key
        )
        await self.ssss.set_encrypted_account_data(
            EventType.CROSS_SIGNING_USER_SIGNING, seeds.user_signing_key, key
        )
        await self.ssss.set_encrypted_account_data(
            EventType.CROSS_SIGNING_SELF_SIGNING, seeds.self_signing_key, key
        )

    async def get_own_cross_signing_public_keys(self) -> CrossSigningPublicKeys | None:
        if self._cross_signing_public_keys or self._cross_signing_public_keys_fetched:
            return self._cross_signing_public_keys
        keys = await self.get_cross_signing_public_keys(self.client.mxid)
        self._cross_signing_public_keys_fetched = True
        if keys:
            self._cross_signing_public_keys = keys
        return keys

    async def get_cross_signing_public_keys(
        self, user_id: UserID
    ) -> CrossSigningPublicKeys | None:
        db_keys = await self.crypto_store.get_cross_signing_keys(user_id)
        if CrossSigningUsage.MASTER not in db_keys and user_id not in self._cs_fetch_attempted:
            self.log.debug(f"Didn't find any cross-signing keys for {user_id}, fetching...")
            async with self._fetch_keys_lock:
                if user_id not in self._cs_fetch_attempted:
                    self._cs_fetch_attempted.add(user_id)
                    await self._fetch_keys([user_id], include_untracked=True)
            db_keys = await self.crypto_store.get_cross_signing_keys(user_id)
        if CrossSigningUsage.MASTER not in db_keys:
            return None
        return CrossSigningPublicKeys(
            master_key=db_keys[CrossSigningUsage.MASTER].key,
            self_signing_key=(
                db_keys[CrossSigningUsage.SELF].key if CrossSigningUsage.SELF in db_keys else None
            ),
            user_signing_key=(
                db_keys[CrossSigningUsage.USER].key if CrossSigningUsage.USER in db_keys else None
            ),
        )

    async def sign_own_device(self, device: DeviceIdentity) -> None:
        full_keys = await self._get_full_device_keys(device)
        ssk = self._cross_signing_private_keys.self_signing_key
        signature = sign_olm(full_keys, ssk)
        full_keys.signatures = {self.client.mxid: {KeyID.ed25519(ssk.public_key): signature}}
        await self.client.upload_one_signature(device.user_id, device.device_id, full_keys)
        await self.crypto_store.put_signature(
            CrossSigner(device.user_id, device.signing_key),
            CrossSigner(self.client.mxid, ssk.public_key),
            signature,
        )

    async def _publish_cross_signing_keys(
        self,
        keys: CrossSigningPrivateKeys,
        auth: dict[str, JSON] | None = None,
    ) -> None:
        public = keys.public_keys
        master_key = CrossSigningKeys(
            user_id=self.client.mxid,
            usage=[CrossSigningUsage.MASTER],
            keys={KeyID.ed25519(public.master_key): public.master_key},
        )
        master_key.signatures = {
            self.client.mxid: {
                KeyID.ed25519(self.client.device_id): sign_olm(master_key, self.account),
            }
        }
        self_key = CrossSigningKeys(
            user_id=self.client.mxid,
            usage=[CrossSigningUsage.SELF],
            keys={KeyID.ed25519(public.self_signing_key): public.self_signing_key},
        )
        self_key.signatures = {
            self.client.mxid: {
                KeyID.ed25519(public.master_key): sign_olm(self_key, keys.master_key),
            }
        }
        user_key = CrossSigningKeys(
            user_id=self.client.mxid,
            usage=[CrossSigningUsage.USER],
            keys={KeyID.ed25519(public.user_signing_key): public.user_signing_key},
        )
        user_key.signatures = {
            self.client.mxid: {
                KeyID.ed25519(public.master_key): sign_olm(user_key, keys.master_key),
            }
        }
        await self.client.upload_cross_signing_keys(
            keys={
                CrossSigningUsage.MASTER: master_key,
                CrossSigningUsage.SELF: self_key,
                CrossSigningUsage.USER: user_key,
            },
            auth=auth,
        )
        await self.crypto_store.put_cross_signing_key(
            self.client.mxid, CrossSigningUsage.MASTER, public.master_key
        )
        await self.crypto_store.put_cross_signing_key(
            self.client.mxid, CrossSigningUsage.SELF, public.self_signing_key
        )
        await self.crypto_store.put_cross_signing_key(
            self.client.mxid, CrossSigningUsage.USER, public.user_signing_key
        )
        self._cross_signing_private_keys = keys
        self._cross_signing_public_keys = public
