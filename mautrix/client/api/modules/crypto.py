# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any

from mautrix.api import Method, Path
from mautrix.errors import MatrixResponseError
from mautrix.types import (
    ClaimKeysResponse,
    DeviceID,
    EncryptionKeyAlgorithm,
    EventType,
    QueryKeysResponse,
    Serializable,
    SyncToken,
    ToDeviceEventContent,
    UserID,
)

from ..base import BaseClientAPI


class CryptoMethods(BaseClientAPI):
    """
    Methods in section `13.9 Send-to-Device messaging <https://matrix.org/docs/spec/client_server/r0.6.1#id70>`__
    and `13.11 End-to-End Encryption of the spec <https://matrix.org/docs/spec/client_server/r0.6.1#id76>`__.
    """

    async def send_to_device(
        self, event_type: EventType, messages: dict[UserID, dict[DeviceID, ToDeviceEventContent]]
    ) -> None:
        """
        Send to-device events to a set of client devices.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#put-matrix-client-r0-sendtodevice-eventtype-txnid>`__

        Args:
            event_type: The type of event to send.
            messages: The messages to send. A map from user ID, to a map from device ID to message
                body. The device ID may also be ``*``, meaning all known devices for the user.
        """
        if not event_type.is_to_device:
            raise ValueError("Event type must be a to-device event type")
        await self.api.request(
            Method.PUT,
            Path.sendToDevice[event_type][self.api.get_txn_id()],
            {
                "messages": {
                    user_id: {
                        device_id: (
                            content.serialize() if isinstance(content, Serializable) else content
                        )
                        for device_id, content in devices.items()
                    }
                    for user_id, devices in messages.items()
                },
            },
        )

    async def send_to_one_device(
        self,
        event_type: EventType,
        user_id: UserID,
        device_id: DeviceID,
        message: ToDeviceEventContent,
    ) -> None:
        """
        Send a to-device event to a single device.

        Args:
            event_type: The type of event to send.
            user_id: The user whose device to send the event to.
            device_id: The device ID to send the event to.
            message: The event content to send.
        """
        return await self.send_to_device(event_type, {user_id: {device_id: message}})

    async def upload_keys(
        self,
        one_time_keys: dict[str, Any] | None = None,
        device_keys: dict[str, Any] | None = None,
    ) -> dict[EncryptionKeyAlgorithm, int]:
        """
        Publishes end-to-end encryption keys for the device.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-keys-upload>`__

        Args:
            one_time_keys: One-time public keys for "pre-key" messages. The names of the properties
                should be in the format ``<algorithm>:<key_id>``. The format of the key is
                determined by the key algorithm.
            device_keys: Identity keys for the device. May be absent if no new identity keys are
                required.

        Returns:
            For each key algorithm, the number of unclaimed one-time keys of that type currently
            held on the server for this device.
        """
        data = {}
        if device_keys:
            data["device_keys"] = device_keys
        if one_time_keys:
            data["one_time_keys"] = one_time_keys
        resp = await self.api.request(Method.POST, Path.keys.upload, data)
        try:
            return {
                EncryptionKeyAlgorithm.deserialize(alg): count
                for alg, count in resp["one_time_key_counts"].items()
            }
        except KeyError as e:
            raise MatrixResponseError("`one_time_key_counts` not in response.") from e
        except AttributeError as e:
            raise MatrixResponseError("Invalid `one_time_key_counts` field in response.") from e

    async def query_keys(
        self,
        device_keys: list[UserID] | set[UserID] | dict[UserID, list[DeviceID]],
        token: SyncToken = "",
        timeout: int = 10000,
    ) -> QueryKeysResponse:
        """
        Fetch devices and their identity keys for the given users.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-keys-query>`__

        Args:
            device_keys: The keys to be downloaded. A map from user ID, to a list of device IDs, or
                to an empty list to indicate all devices for the corresponding user.
            token: If the client is fetching keys as a result of a device update received in a sync
                request, this should be the 'since' token of that sync request, or any later sync
                token. This allows the server to ensure its response contains the keys advertised by
                the notification in that sync.
            timeout: The time (in milliseconds) to wait when downloading keys from remote servers.

        Returns:
            Information on the queried devices and errors for homeservers that could not be reached.
        """
        if isinstance(device_keys, (list, set)):
            device_keys = {user_id: [] for user_id in device_keys}
        data = {
            "timeout": timeout,
            "device_keys": device_keys,
        }
        if token:
            data["token"] = token
        resp = await self.api.request(Method.POST, Path.keys.query, data)
        return QueryKeysResponse.deserialize(resp)

    async def claim_keys(
        self,
        one_time_keys: dict[UserID, dict[DeviceID, EncryptionKeyAlgorithm]],
        timeout: int = 10000,
    ) -> ClaimKeysResponse:
        """
        Claim one-time keys for use in pre-key messages.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-keys-claim>`__

        Args:
            one_time_keys: The keys to be claimed. A map from user ID, to a map from device ID to
                algorithm name.
            timeout: The time (in milliseconds) to wait when downloading keys from remote servers.

        Returns:
            One-time keys for the queried devices and errors for homeservers that could not be
            reached.
        """
        resp = await self.api.request(
            Method.POST,
            Path.keys.claim,
            {
                "timeout": timeout,
                "one_time_keys": {
                    user_id: {device_id: alg.serialize() for device_id, alg in devices.items()}
                    for user_id, devices in one_time_keys.items()
                },
            },
        )
        return ClaimKeysResponse.deserialize(resp)
