# Copyright © 2019 Damir Jelić <poljar@termina.org.uk> (under the Apache 2.0 license)
# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest
import unpaddedbase64

from mautrix.errors import DecryptionError

from .attachments import decrypt_attachment, encrypt_attachment, inplace_encrypt_attachment

try:
    from Crypto import Random
except ImportError:
    from Cryptodome import Random


def test_encrypt():
    data = b"Test bytes"

    cyphertext, keys = encrypt_attachment(data)

    plaintext = decrypt_attachment(cyphertext, keys.key.key, keys.hashes["sha256"], keys.iv)

    assert data == plaintext


def test_inplace_encrypt():
    orig_data = b"Test bytes"
    data = bytearray(orig_data)

    keys = inplace_encrypt_attachment(data)

    assert data != orig_data

    decrypt_attachment(data, keys.key.key, keys.hashes["sha256"], keys.iv, inplace=True)

    assert data == orig_data


def test_hash_verification():
    data = b"Test bytes"

    cyphertext, keys = encrypt_attachment(data)

    with pytest.raises(DecryptionError):
        decrypt_attachment(cyphertext, keys.key.key, "Fake hash", keys.iv)


def test_invalid_key():
    data = b"Test bytes"

    cyphertext, keys = encrypt_attachment(data)

    with pytest.raises(DecryptionError):
        decrypt_attachment(cyphertext, "Fake key", keys.hashes["sha256"], keys.iv)


def test_invalid_iv():
    data = b"Test bytes"

    cyphertext, keys = encrypt_attachment(data)

    with pytest.raises(DecryptionError):
        decrypt_attachment(cyphertext, keys.key.key, keys.hashes["sha256"], "Fake iv")


def test_short_key():
    data = b"Test bytes"

    cyphertext, keys = encrypt_attachment(data)

    with pytest.raises(DecryptionError):
        decrypt_attachment(
            cyphertext,
            unpaddedbase64.encode_base64(b"Fake key", urlsafe=True),
            keys["hashes"]["sha256"],
            keys["iv"],
        )


def test_short_iv():
    data = b"Test bytes"

    cyphertext, keys = encrypt_attachment(data)

    with pytest.raises(DecryptionError):
        decrypt_attachment(
            cyphertext,
            keys.key.key,
            keys.hashes["sha256"],
            unpaddedbase64.encode_base64(b"F" + b"\x00" * 8),
        )


def test_fake_key():
    data = b"Test bytes"

    cyphertext, keys = encrypt_attachment(data)

    fake_key = Random.new().read(32)

    plaintext = decrypt_attachment(
        cyphertext,
        unpaddedbase64.encode_base64(fake_key, urlsafe=True),
        keys["hashes"]["sha256"],
        keys["iv"],
    )
    assert plaintext != data
