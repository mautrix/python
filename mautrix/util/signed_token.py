# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Optional
from hashlib import sha256
import base64
import hmac
import json


def _get_checksum(key: str, payload: bytes) -> str:
    hasher = hmac.new(key.encode("utf-8"), msg=payload, digestmod=sha256)
    checksum = base64.urlsafe_b64encode(hasher.digest())
    return checksum.decode("utf-8").rstrip("=")


def sign_token(key: str, payload: Dict) -> str:
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    checksum = _get_checksum(key, payload_b64)
    payload_str = payload_b64.decode("utf-8").rstrip("=")
    return f"{checksum}:{payload_str}"


def verify_token(key: str, data: str) -> Optional[Dict]:
    if not data:
        return None

    try:
        checksum, payload = data.split(":", 1)
    except ValueError:
        return None

    payload += (3 - (len(payload) + 3) % 4) * "="

    if checksum != _get_checksum(key, payload.encode("utf-8")):
        return None

    payload = base64.urlsafe_b64decode(payload).decode("utf-8")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None
