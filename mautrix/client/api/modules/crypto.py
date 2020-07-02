# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Dict, Any

from mautrix.errors import MatrixResponseError
from mautrix.api import Method, Path

from ..types import (UserID, DeviceID, EncryptionAlgorithm, EncryptionKeyAlgorithm,
                     ClaimKeysResponse, QueryKeysResponse)
from ..base import BaseClientAPI


class CryptoMethods(BaseClientAPI):
    """
    Methods in section 13.11 End-to-End Encryption of the spec. These methods are used for setting and getting user
    metadata and searching for users.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#id76>`__
    """

    async def upload_keys(self, one_time_keys: Dict[str, Any]) -> Dict[EncryptionKeyAlgorithm, int]:
        """
        Publishes one-time end-to-end encryption keys for the device.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-keys-upload>`__

        Args:
            one_time_keys: One-time public keys for "pre-key" messages. The names of the properties
                should be in the format ``<algorithm>:<key_id>``. The format of the key is
                determined by the key algorithm.

        Returns:
            For each key algorithm, the number of unclaimed one-time keys of that type currently
            held on the server for this device.
        """
        resp = await self.api.request(Method.POST, Path.keys.upload, {
            "one_time_keys": one_time_keys,
        })
        try:
            return {EncryptionKeyAlgorithm.deserialize(alg): count
                    for alg, count in resp["one_time_key_counts"].items()}
        except KeyError as e:
            raise MatrixResponseError("`one_time_key_counts` not in response.") from e
        except AttributeError as e:
            raise MatrixResponseError("Invalid `one_time_key_counts` field in response.") from e

    async def upload_device_keys(self, algorithms: List[EncryptionAlgorithm], keys: Dict[str, str],
                                 signatures: Dict[str, Any]) -> None:
        """
        Publishes the identity and signature end-to-end encryption keys for the device.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-keys-upload>`__

        Args:
            algorithms: The encryption algorithms supported by this device.
            keys: Public identity keys. The names of the properties should be in the format
                ``<algorithm>:<device_id>``. The keys themselves should be encoded as specified by
                the key algorithm.
            signatures: Signatures for the device key object. A map from user ID, to a map from
                ``<algorithm>:<device_id>`` to the signature.
        """
        await self.api.request(Method.POST, Path.keys.upload, {
            "device_keys": {
                "user_id": self.mxid,
                "device_id": self.device_id,
                "algorithms": [alg.serialize() for alg in algorithms],
                "keys": keys,
                "signatures": signatures,
            },
        })

    async def query_keys(self, device_keys: Dict[UserID, List[DeviceID]], timeout: int = 10000
                         ) -> QueryKeysResponse:
        """
        Fetch devices and their identity keys for the given users.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-keys-query>`__

        Args:
            device_keys: The keys to be downloaded. A map from user ID, to a list of device IDs, or
                to an empty list to indicate all devices for the corresponding user.
            timeout: The time (in milliseconds) to wait when downloading keys from remote servers.

        Returns:
            Information on the queried devices and errors for homeservers that could not be reached.
        """
        resp = await self.api.request(Method.POST, Path.keys.query, {
            "timeout": timeout,
            "device_keys": device_keys,
        })
        return QueryKeysResponse.deserialize(resp)

    async def claim_keys(self, one_time_keys: Dict[UserID, Dict[DeviceID, EncryptionKeyAlgorithm]],
                         timeout: int = 10000) -> ClaimKeysResponse:
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
        resp = await self.api.request(Method.POST, Path.keys.claim, {
            "timeout": timeout,
            "one_time_keys": one_time_keys,
        })
        return ClaimKeysResponse.deserialize(resp)
