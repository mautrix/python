# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, List, Union
import json

from mautrix.types import (EncryptedMegolmEventContent, EventType, UserID, DeviceID, Serializable,
                           EncryptionAlgorithm, RoomID, EncryptedToDeviceEventContent, SessionID,
                           RoomKeyWithheldEventContent, RoomKeyWithheldCode, IdentityKey,
                           SigningKey, RelatesTo, MessageEvent)

from .types import DeviceIdentity, TrustState, EncryptionError
from .base import BaseOlmMachine
from .sessions import OutboundGroupSession, InboundGroupSession


class MegolmDecryptionMachine(BaseOlmMachine):
    async def decrypt_megolm_event(self, evt: MessageEvent) -> MessageEvent:
        pass
