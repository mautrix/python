# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import NewType, Union, Dict, List

JSON = NewType("JSON", Union[str, int, float, bool, None, Dict[str, 'JSON'], List['JSON']])

UserID = NewType("UserID", str)
EventID = NewType("EventID", str)
RoomID = NewType("RoomID", str)
RoomAlias = NewType("RoomAlias", str)

FilterID = NewType("FilterID", str)

ContentURI = NewType("ContentURI", str)

SyncToken = NewType("SyncToken", str)

DeviceID = NewType("DeviceID", str)
SessionID = NewType("SessionID", str)
SigningKey = NewType("SigningKey", str)  # ed25519
IdentityKey = NewType("IdentityKey", str)  # curve25519
