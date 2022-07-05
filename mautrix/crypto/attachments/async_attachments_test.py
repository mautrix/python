# Copyright © 2019 Damir Jelić <poljar@termina.org.uk> (under the Apache 2.0 license)
# Copyright © 2019 miruka <miruka@disroot.org> (under the Apache 2.0 license)
# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.types import EncryptedFile

from .async_attachments import async_encrypt_attachment, async_inplace_encrypt_attachment
from .attachments import decrypt_attachment

try:
    from Crypto import Random
except ImportError:
    from Cryptodome import Random


async def _get_data_cypher_keys(data: bytes) -> tuple[bytes, EncryptedFile]:
    *chunks, keys = [i async for i in async_encrypt_attachment(data)]
    return b"".join(chunks), keys


async def test_async_encrypt():
    data = b"Test bytes"

    cyphertext, keys = await _get_data_cypher_keys(data)

    plaintext = decrypt_attachment(cyphertext, keys.key.key, keys.hashes["sha256"], keys.iv)

    assert data == plaintext


async def test_async_inplace_encrypt():
    orig_data = b"Test bytes"
    data = bytearray(orig_data)

    keys = await async_inplace_encrypt_attachment(data)

    assert data != orig_data

    decrypt_attachment(data, keys.key.key, keys.hashes["sha256"], keys.iv, inplace=True)

    assert data == orig_data
