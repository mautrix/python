# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, NewType, Union

JSON = NewType("JSON", Union[str, int, float, bool, None, Dict[str, "JSON"], List["JSON"]])
JSON.__doc__ = "A union type that covers all JSON-serializable data."

UserID = NewType("UserID", str)
UserID.__doc__ = "A Matrix user ID (``@user:example.com``)"
EventID = NewType("EventID", str)
EventID.__doc__ = "A Matrix event ID (``$base64`` or ``$legacyid:example.com``)"
RoomID = NewType("RoomID", str)
RoomID.__doc__ = "An internal Matrix room ID (``!randomstring:example.com``)"
RoomAlias = NewType("RoomAlias", str)
RoomAlias.__doc__ = "A Matrix room address (``#alias:example.com``)"

FilterID = NewType("FilterID", str)
FilterID.__doc__ = """
A filter ID returned by ``POST /filter`` (:meth:`mautrix.client.ClientAPI.create_filter`)
"""

BatchID = NewType("BatchID", str)
BatchID.__doc__ = """
A message batch ID returned by ``POST /batch_send`` (:meth:`mautrix.appservice.IntentAPI.batch_send`)
"""

ContentURI = NewType("ContentURI", str)
ContentURI.__doc__ = """
A Matrix `content URI`_, used by the content repository.

.. _content URI:
    https://spec.matrix.org/v1.2/client-server-api/#matrix-content-mxc-uris
"""

SyncToken = NewType("SyncToken", str)
SyncToken.__doc__ = """
A ``next_batch`` token from a ``/sync`` response (:meth:`mautrix.client.ClientAPI.sync`)
"""

DeviceID = NewType("DeviceID", str)
DeviceID.__doc__ = "A Matrix device ID. Arbitrary, potentially client-specified string."
SessionID = NewType("SessionID", str)
SessionID.__doc__ = """
A `Megolm`_ session ID.

.. _Megolm:
    https://gitlab.matrix.org/matrix-org/olm/-/blob/master/docs/megolm.md
"""
SigningKey = NewType("SigningKey", str)
SigningKey.__doc__ = "A ed25519 public key as unpadded base64"
IdentityKey = NewType("IdentityKey", str)
IdentityKey.__doc__ = "A curve25519 public key as unpadded base64"
Signature = NewType("Signature", str)
Signature.__doc__ = "An ed25519 signature as unpadded base64"
