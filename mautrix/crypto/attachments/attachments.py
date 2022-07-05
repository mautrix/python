# Copyright 2018 Zil0 (under the Apache 2.0 license)
# Copyright © 2019 Damir Jelić <poljar@termina.org.uk> (under the Apache 2.0 license)
# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import annotations

from typing import Generator, Iterable
import binascii
import struct

import unpaddedbase64

from mautrix.errors import DecryptionError
from mautrix.types import EncryptedFile, JSONWebKey

try:
    from Crypto import Random
    from Crypto.Cipher import AES
    from Crypto.Hash import SHA256
    from Crypto.Util import Counter
except ImportError:
    from Cryptodome import Random
    from Cryptodome.Cipher import AES
    from Cryptodome.Hash import SHA256
    from Cryptodome.Util import Counter


def decrypt_attachment(
    ciphertext: bytes | bytearray | memoryview, key: str, hash: str, iv: str, inplace: bool = False
) -> bytes:
    """Decrypt an encrypted attachment.

    Args:
        ciphertext: The data to decrypt.
        key: AES_CTR JWK key object.
        hash: Base64 encoded SHA-256 hash of the ciphertext.
        iv: Base64 encoded 16 byte AES-CTR IV.
        inplace: Should the decryption be performed in-place?
                 The input must be a bytearray or writable memoryview to use this.
    Returns:
        The plaintext bytes.
    Raises:
        EncryptionError: if the integrity check fails.
    """
    expected_hash = unpaddedbase64.decode_base64(hash)

    h = SHA256.new()
    h.update(ciphertext)

    if h.digest() != expected_hash:
        raise DecryptionError("Mismatched SHA-256 digest")

    try:
        byte_key: bytes = unpaddedbase64.decode_base64(key)
    except (binascii.Error, TypeError):
        raise DecryptionError("Error decoding key")

    try:
        byte_iv: bytes = unpaddedbase64.decode_base64(iv)
        if len(byte_iv) != 16:
            raise DecryptionError("Invalid IV length")
        prefix = byte_iv[:8]
        # A non-zero IV counter is not spec-compliant, but some clients still do it,
        # so decode the counter part too.
        initial_value = struct.unpack(">Q", byte_iv[8:])[0]
    except (binascii.Error, TypeError, IndexError, struct.error):
        raise DecryptionError("Error decoding IV")

    ctr = Counter.new(64, prefix=prefix, initial_value=initial_value)

    try:
        cipher = AES.new(byte_key, AES.MODE_CTR, counter=ctr)
    except ValueError as e:
        raise DecryptionError("Failed to create AES cipher") from e

    if inplace:
        cipher.decrypt(ciphertext, ciphertext)
        return ciphertext
    else:
        return cipher.decrypt(ciphertext)


def encrypt_attachment(plaintext: bytes) -> tuple[bytes, EncryptedFile]:
    """Encrypt data in order to send it as an encrypted attachment.

    Args:
        plaintext: The data to encrypt.

    Returns:
        A tuple with the encrypted bytes and a dict containing the info needed
        to decrypt data. See ``encrypted_attachment_generator()`` for the keys.
    """
    values = list(encrypted_attachment_generator(plaintext))
    return b"".join(values[:-1]), values[-1]


def _prepare_encryption() -> tuple[bytes, bytes, AES, SHA256.SHA256Hash]:
    key = Random.new().read(32)
    # 8 bytes IV
    iv = Random.new().read(8)
    # 8 bytes counter, prefixed by the IV
    ctr = Counter.new(64, prefix=iv, initial_value=0)

    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    sha256 = SHA256.new()

    return key, iv, cipher, sha256


def inplace_encrypt_attachment(data: bytearray | memoryview) -> EncryptedFile:
    key, iv, cipher, sha256 = _prepare_encryption()

    cipher.encrypt(plaintext=data, output=data)
    sha256.update(data)

    return _get_decryption_info(key, iv, sha256)


def encrypted_attachment_generator(
    data: bytes | Iterable[bytes],
) -> Generator[bytes | EncryptedFile, None, None]:
    """Generator to encrypt data in order to send it as an encrypted
    attachment.

    Unlike ``encrypt_attachment()``, this function lazily encrypts and yields
    data, thus it can be used to encrypt large files without fully loading them
    into memory if an iterable of bytes is passed as data.

    Args:
        data: The data to encrypt.

    Yields:
        The encrypted bytes for each chunk of data.
        The last yielded value will be a dict containing the info needed to decrypt data.
    """

    key, iv, cipher, sha256 = _prepare_encryption()

    if isinstance(data, bytes):
        data = [data]

    for chunk in data:
        encrypted_chunk = cipher.encrypt(chunk)  # in executor
        sha256.update(encrypted_chunk)  # in executor
        yield encrypted_chunk

    yield _get_decryption_info(key, iv, sha256)


def _get_decryption_info(key: bytes, iv: bytes, sha256: SHA256.SHA256Hash) -> EncryptedFile:
    return EncryptedFile(
        version="v2",
        iv=unpaddedbase64.encode_base64(iv + b"\x00" * 8),
        hashes={"sha256": unpaddedbase64.encode_base64(sha256.digest())},
        key=JSONWebKey(
            key_type="oct",
            algorithm="A256CTR",
            extractable=True,
            key_ops=["encrypt", "decrypt"],
            key=unpaddedbase64.encode_base64(key, urlsafe=True),
        ),
    )
