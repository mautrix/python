from typing import Dict, Optional
import json
import base64
import hashlib


def _get_checksum(key: str, payload: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(payload)
    hasher.update(key.encode("utf-8"))
    checksum = hasher.hexdigest()
    return checksum


def sign_token(key: str, payload: Dict) -> str:
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    checksum = _get_checksum(key, payload_b64)
    return f"{checksum}:{payload_b64.decode('utf-8')}"


def verify_token(key: str, data: str) -> Optional[Dict]:
    if not data:
        return None

    try:
        checksum, payload = data.split(":", 1)
    except ValueError:
        return None

    if checksum != _get_checksum(key, payload.encode("utf-8")):
        return None

    payload = base64.urlsafe_b64decode(payload).decode("utf-8")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None
