# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from mautrix import client as cli
from mautrix.errors import MNotFound
from mautrix.types import EventType, SecretStorageDefaultKeyEventContent

from .key import Key, KeyMetadata
from .types import EncryptedAccountDataEventContent


class Machine:
    client: cli.Client

    def __init__(self, client: cli.Client) -> None:
        self.client = client

    async def get_default_key_id(self) -> str | None:
        try:
            data = await self.client.get_account_data(EventType.SECRET_STORAGE_DEFAULT_KEY)
            return SecretStorageDefaultKeyEventContent.deserialize(data).key
        except (MNotFound, ValueError):
            return None

    async def set_default_key_id(self, key_id: str) -> None:
        await self.client.set_account_data(
            EventType.SECRET_STORAGE_DEFAULT_KEY,
            SecretStorageDefaultKeyEventContent(key=key_id),
        )

    async def get_key_data(self, key_id: str) -> KeyMetadata:
        data = await self.client.get_account_data(f"m.secret_storage.key.{key_id}")
        return KeyMetadata.deserialize(data)

    async def set_key_data(self, key_id: str, data: KeyMetadata) -> None:
        await self.client.set_account_data(f"m.secret_storage.key.{key_id}", data)

    async def get_default_key_data(self) -> tuple[str, KeyMetadata]:
        key_id = await self.get_default_key_id()
        if not key_id:
            raise ValueError("No default key ID set")
        return key_id, await self.get_key_data(key_id)

    async def get_decrypted_account_data(self, event_type: EventType | str, key: Key) -> bytes:
        data = await self.client.get_account_data(event_type)
        parsed = EncryptedAccountDataEventContent.deserialize(data)
        return parsed.decrypt(event_type, key)

    async def set_encrypted_account_data(
        self, event_type: EventType | str, data: bytes, *keys: Key
    ) -> None:
        encrypted_data = {}
        for key in keys:
            encrypted_data[key.id] = key.encrypt(event_type, data)
        await self.client.set_account_data(
            event_type,
            EncryptedAccountDataEventContent(encrypted=encrypted_data),
        )

    async def generate_and_upload_key(self, passphrase: str | None = None) -> Key:
        key = Key.generate(passphrase)
        await self.set_key_data(key.id, key.metadata)
        return key
