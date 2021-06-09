# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, ClassVar
import logging
import time

from attr import dataclass
import aiohttp

from mautrix.types import SerializableAttrs, UserID


@dataclass(kw_only=True)
class BridgeState(SerializableAttrs['BridgeState']):
    human_readable_errors: ClassVar[Dict[str, str]] = {}

    user_id: UserID = None
    remote_id: str = None
    remote_name: str = None
    ok: bool
    timestamp: int = None
    ttl: int = 0
    error_source: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None

    def fill(self) -> 'BridgeState':
        if not self.timestamp:
            self.timestamp = int(time.time())
        if not self.ok:
            self.error_source = "bridge"
            try:
                msg = self.human_readable_errors[self.error]
            except KeyError:
                pass
            else:
                self.message = msg.format(message=self.message) if self.message else msg
            if not self.ttl:
                self.ttl = 60
        else:
            self.error = None
            self.error_source = None
            if not self.ttl:
                self.ttl = 240
        return self

    def should_deduplicate(self, prev_state: 'BridgeState') -> bool:
        if not prev_state or prev_state.ok != self.ok or prev_state.error != self.error:
            # If there's no previous state or the state was different, send this one.
            return False
        # If there's more than ⅘ of the previous pong's time-to-live left, drop this one
        return prev_state.timestamp + (prev_state.ttl / 5) > self.timestamp

    async def send(self, url: str, token: str, log: logging.Logger) -> None:
        if not url:
            return
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with aiohttp.ClientSession() as sess, sess.post(url, json=self.serialize(),
                                                                  headers=headers) as resp:
                if not 200 <= resp.status < 300:
                    text = await resp.text()
                    text = text.replace("\n", "\\n")
                    log.warning(f"Unexpected status code {resp.status} "
                                f"sending bridge state update: {text}")
                else:
                    log.debug(f"Sent new bridge state {self}")
        except Exception as e:
            log.warning(f"Failed to send updated bridge state: {e}")
