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

from mautrix.types import SerializableAttrs, SerializableEnum, UserID


class BridgeStateEvent(SerializableEnum):
    # Bridge process is starting up (will not have valid remoteID)
    STARTING = "STARTING"
    # Bridge has started but has no valid credentials (will not have valid remoteID)
    UNCONFIGURED = "UNCONFIGURED"
    # Bridge has credentials and has started connecting to a remote network
    CONNECTING = "CONNECTING"
    # Bridge has begun backfilling
    BACKFILLING = "BACKFILLING"
    # Bridge has happily connected and is bridging messages
    CONNECTED = "CONNECTED"
    # Bridge has temporarily disconnected, expected to reconnect automatically
    TRANSIENT_DISCONNECT = "TRANSIENT_DISCONNECT"
    # Bridge has disconnected, will require user to log in again
    BAD_CREDENTIALS = "BAD_CREDENTIALS"
    # Bridge has disconnected for an unknown/unexpected reason - we should investigate
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    # User has logged out - stop tracking this remote
    LOGGED_OUT = "LOGGED_OUT"


@dataclass(kw_only=True)
class BridgeState(SerializableAttrs):
    human_readable_errors: ClassVar[Dict[Optional[str], str]] = {}
    default_source: ClassVar[str] = "bridge"
    default_error_ttl: ClassVar[int] = 60
    default_ok_ttl: ClassVar[int] = 240

    state_event: BridgeStateEvent
    user_id: Optional[UserID] = None
    remote_id: Optional[str] = None
    remote_name: Optional[str] = None
    timestamp: Optional[int] = None
    ttl: int = 0
    source: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None

    def fill(self) -> 'BridgeState':
        self.timestamp = self.timestamp or int(time.time())

        if self.state_event == BridgeStateEvent.CONNECTED:
            self.error = None
            self.source = None
            self.ttl = self.ttl or self.default_ok_ttl
        elif self.state_event in (
            BridgeStateEvent.STARTING,
            BridgeStateEvent.UNCONFIGURED,
            BridgeStateEvent.CONNECTING,
            BridgeStateEvent.BACKFILLING,
            BridgeStateEvent.LOGGED_OUT,
        ):
            self.error = None
            self.source = None
            self.ttl = self.ttl or self.default_ok_ttl
        else:
            self.source = self.source or self.default_source
            self.ttl = self.ttl or self.default_error_ttl
            try:
                msg = self.human_readable_errors[self.error]
            except KeyError:
                pass
            else:
                self.message = msg.format(message=self.message) if self.message else msg
        return self

    def should_deduplicate(self, prev_state: Optional['BridgeState']) -> bool:
        if (
            not prev_state
            or prev_state.state_event != self.state_event
            or prev_state.error != self.error
        ):
            # If there's no previous state or the state was different, send this one.
            return False
        # If there's more than ⅘ of the previous pong's time-to-live left, drop this one
        return prev_state.timestamp + (prev_state.ttl / 5) > self.timestamp

    async def send(self, url: str, token: str, log: logging.Logger, log_sent: bool = True) -> None:
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
                elif log_sent:
                    log.debug(f"Sent new bridge state {self}")
        except Exception as e:
            log.warning(f"Failed to send updated bridge state: {e}")
