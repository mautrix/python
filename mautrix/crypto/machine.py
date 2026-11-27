# Copyright (c) 2026 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

from yarl import URL

from mautrix import gothon
from mautrix.errors import DecryptionError, EncryptionError, SessionNotFound
from mautrix.types import (
    EncryptedEvent,
    EncryptedMegolmEventContent,
    Event,
    EventContent,
    EventType,
    RoomID,
    Serializable,
    SigningKey,
    TrustState,
)
from mautrix.util.logging import TraceLogger

if TYPE_CHECKING:
    from mautrix.client import Client


class CrossSigningPublicKeys(NamedTuple):
    master_key: SigningKey
    self_signing_key: SigningKey
    user_signing_key: SigningKey


def _database_params(url: str) -> dict[str, str]:
    parsed = URL(url)
    if parsed.scheme in ("postgres", "postgresql"):
        return {"type": "postgres", "uri": url}
    elif parsed.scheme in ("sqlite", "sqlite3"):
        return {"type": "sqlite3-fk-wal", "uri": f"file:{parsed.path}?_txlock=immediate"}
    raise ValueError(f"Unsupported database scheme {parsed.scheme}")


class OlmMachine:
    """
    OlmMachine handles end-to-end encryption for a :class:`mautrix.client.Client` using the
    mautrix-go crypto module.

    The machine stores its keys in the given database, which uses the same schema as mautrix-go.
    Multiple machines can share a database by using different account IDs.
    """

    client: Client
    log: TraceLogger
    database_url: str
    pickle_key: str
    account_id: str
    fingerprint: str | None
    """The fingerprint of the device's signing key. Set after :meth:`start`."""

    def __init__(
        self,
        client: Client,
        database_url: str,
        pickle_key: str,
        account_id: str = "",
        log: TraceLogger | None = None,
    ) -> None:
        """
        Args:
            client: The client to handle encryption for.
            database_url: A ``postgres://`` or ``sqlite:`` URL to store keys in.
            pickle_key: The key to encrypt olm pickles with.
            account_id: The ID of this machine's data in the database.
            log: The logger to use. Defaults to the client's ``crypto_log``.
        """
        self.client = client
        self.log = log or client.crypto_log
        self.database_url = database_url
        self.pickle_key = pickle_key
        self.account_id = account_id
        self.fingerprint = None

    async def _call(self, method: str, **params: Any) -> Any:
        result, _ = await gothon.get_runtime().call(
            method, {"client_id": self.client.api.client_id, **params}
        )
        return result

    async def start(self) -> None:
        """
        Load the olm account from the database, creating and uploading device keys if necessary.
        After this, /sync responses received by the client are passed to the machine.

        Raises:
            GoError: If the database contains a different device ID than the client.
        """
        result = await self._call(
            "crypto.init",
            user_id=self.client.mxid,
            device_id=self.client.device_id,
            access_token=self.client.api.token,
            database=_database_params(self.database_url),
            account_id=self.account_id,
            pickle_key=self.pickle_key,
            log=gothon.log_params(self.log),
        )
        self.fingerprint = result["fingerprint"]

    async def stop(self) -> None:
        """Stop passing /sync responses to the machine and release it."""
        await self._call("crypto.close")

    async def encrypt_megolm_event(
        self, room_id: RoomID, event_type: EventType, content: EventContent | dict[str, Any]
    ) -> EncryptedMegolmEventContent:
        """
        Encrypt an event for a room. Creates and shares a new group session if necessary.

        Args:
            room_id: The room to encrypt the event for.
            event_type: The type of the event.
            content: The content of the event.

        Returns:
            The content of the encrypted event.
        """
        if isinstance(content, Serializable):
            content = content.serialize()
        try:
            result = await self._call(
                "crypto.encrypt", room_id=room_id, event_type=str(event_type), content=content
            )
        except gothon.GoError as e:
            if e.type == "encryption":
                raise EncryptionError(str(e)) from e
            raise
        return EncryptedMegolmEventContent.deserialize(result)

    async def decrypt_megolm_event(
        self, evt: EncryptedEvent, wait_for_session: bool = False
    ) -> Event:
        """
        Decrypt an event.

        Args:
            evt: The encrypted event.
            wait_for_session: If the session isn't known yet, wait for it to arrive and request
                it from other devices.

        Returns:
            The decrypted event.
        """
        try:
            result = await self._call(
                "crypto.decrypt", event=evt.serialize(), wait_for_session=wait_for_session
            )
        except gothon.GoError as e:
            if e.type == "session_not_found":
                raise SessionNotFound(evt.content.session_id, evt.content._sender_key) from e
            elif e.type == "decryption":
                raise DecryptionError(str(e)) from e
            raise
        decrypted = Event.deserialize(result["event"])
        decrypted.unsigned = evt.unsigned
        decrypted.type = decrypted.type.with_class(evt.type.t_class)
        decrypted["mautrix"] = {
            "trust_state": TrustState(result["trust_state"]),
            "forwarded_keys": result["forwarded_keys"],
            "was_encrypted": True,
        }
        return decrypted

    async def verify_with_recovery_key(self, recovery_key: str) -> None:
        """Fetch the cross-signing keys from SSSS with a recovery key and sign this device."""
        await self._call("crypto.verify_with_recovery_key", recovery_key=recovery_key)

    async def generate_recovery_key(self) -> str:
        """
        Generate and upload new cross-signing keys, and sign this device with them.

        Returns:
            The recovery key for the new SSSS key that the cross-signing keys are stored in.
        """
        result = await self._call("crypto.generate_recovery_key")
        return result["recovery_key"]

    async def get_own_cross_signing_public_keys(self) -> CrossSigningPublicKeys | None:
        """Get the public cross-signing keys of the client's user, if they have any."""
        result = await self._call("crypto.get_own_cross_signing_public_keys")
        if not result:
            return None
        return CrossSigningPublicKeys(**result)

    async def get_own_trust_state(self) -> TrustState:
        """Get the trust state of this device."""
        result = await self._call("crypto.get_own_trust_state")
        return TrustState(result["trust_state"])
