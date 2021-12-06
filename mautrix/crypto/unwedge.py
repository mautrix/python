# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import time

from mautrix.types import EventType, IdentityKey, Obj, UserID

from .decrypt_olm import OlmDecryptionMachine
from .device_lists import DeviceListMachine
from .encrypt_olm import OlmEncryptionMachine

MIN_UNWEDGE_INTERVAL = 1 * 60 * 60


class OlmUnwedgingMachine(OlmDecryptionMachine, OlmEncryptionMachine, DeviceListMachine):
    async def _unwedge_session(self, sender: UserID, sender_key: IdentityKey) -> None:
        try:
            prev_unwedge = self._prev_unwedge[sender_key]
        except KeyError:
            pass
        else:
            delta = time.monotonic() - prev_unwedge
            if delta < MIN_UNWEDGE_INTERVAL:
                self.log.debug(
                    f"Not creating new Olm session with {sender}/{sender_key}, "
                    f"previous recreation was {delta}s ago"
                )
                return
        self._prev_unwedge[sender_key] = time.monotonic()
        try:
            device = await self.get_or_fetch_device_by_key(sender, sender_key)
            if device is None:
                self.log.warning(
                    f"Didn't find identity of {sender}/{sender_key}, can't unwedge session"
                )
                return
            self.log.debug(
                f"Creating new Olm session with {sender}/{device.user_id} (key: {sender_key})"
            )
            await self.send_encrypted_to_device(
                device, EventType.TO_DEVICE_DUMMY, Obj(), _force_recreate_session=True
            )
        except Exception:
            self.log.exception(f"Error unwedging session with {sender}/{sender_key}")
