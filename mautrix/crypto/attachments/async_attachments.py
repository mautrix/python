# Copyright © 2018, 2019 Damir Jelić <poljar@termina.org.uk>
# Copyright © 2019 miruka <miruka@disroot.org>
#
# Permission to use, copy, modify, and/or distribute this software for
# any purpose with or without fee is hereby granted, provided that the
# above copyright notice and this permission notice appear in all copies.
#
# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import AsyncGenerator, AsyncIterable, Iterable
from functools import partial
import asyncio
import io

from mautrix.types import EncryptedFile

from .attachments import _get_decryption_info, _prepare_encryption, inplace_encrypt_attachment


async def async_encrypt_attachment(
    data: bytes | Iterable[bytes] | AsyncIterable[bytes] | io.BufferedIOBase,
) -> AsyncGenerator[bytes | EncryptedFile, None]:
    """Async generator to encrypt data in order to send it as an encrypted
    attachment.

    This function lazily encrypts and yields data, thus it can be used to
    encrypt large files without fully loading them into memory if an iterable
    or async iterable of bytes is passed as data.

    Args:
        data: The data to encrypt.
            Passing an async iterable allows the file data to be read in an asynchronous and lazy
            (without reading the entire file into memory) way.
            Passing a non-async iterable or standard open binary file object will still allow the
            data to be read lazily, but not asynchronously.

    Yields:
        The encrypted bytes for each chunk of data.
        The last yielded value will be a dict containing the info needed to
        decrypt data. The keys are:
        | key: AES-CTR JWK key object.
        | iv: Base64 encoded 16 byte AES-CTR IV.
        | hashes.sha256: Base64 encoded SHA-256 hash of the ciphertext.
    """

    key, iv, cipher, sha256 = _prepare_encryption()

    loop = asyncio.get_running_loop()

    async for chunk in async_generator_from_data(data):
        update_crypt = partial(cipher.encrypt, chunk)
        crypt_chunk = await loop.run_in_executor(None, update_crypt)

        update_hash = partial(sha256.update, crypt_chunk)
        await loop.run_in_executor(None, update_hash)

        yield crypt_chunk

    yield _get_decryption_info(key, iv, sha256)


async def async_inplace_encrypt_attachment(data: bytearray) -> EncryptedFile:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(inplace_encrypt_attachment, data))


async def async_generator_from_data(
    data: bytes | Iterable[bytes] | AsyncIterable[bytes] | io.BufferedIOBase,
    chunk_size: int = 4 * 1024,
) -> AsyncGenerator[bytes, None]:
    if isinstance(data, bytes):
        chunks = (data[i : i + chunk_size] for i in range(0, len(data), chunk_size))
        for chunk in chunks:
            yield chunk
    elif isinstance(data, io.BufferedIOBase):
        while True:
            chunk = data.read(chunk_size)
            if not chunk:
                return
            yield chunk
    elif isinstance(data, Iterable):
        for chunk in data:
            yield chunk
    elif isinstance(data, AsyncIterable):
        async for chunk in data:
            yield chunk
    else:
        raise TypeError(f"Unknown type for data: {data!r}")
