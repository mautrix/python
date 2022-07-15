# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, ClassVar, Dict, Optional
import logging
import time

from attr import dataclass
import aiohttp

from mautrix.api import HTTPAPI
from mautrix.types import SerializableAttrs, SerializableEnum, UserID, field


class BridgeStateEvent(SerializableEnum):
    #####################################
    # Global state events, no remote ID #
    #####################################

    # Bridge process is starting up
    STARTING = "STARTING"
    # Bridge has started but has no valid credentials
    UNCONFIGURED = "UNCONFIGURED"
    # Bridge is running
    RUNNING = "RUNNING"
    # The server was unable to reach the bridge
    BRIDGE_UNREACHABLE = "BRIDGE_UNREACHABLE"

    ################################################
    # Remote state events, should have a remote ID #
    ################################################

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


ok_ish_states = (
    BridgeStateEvent.STARTING,
    BridgeStateEvent.UNCONFIGURED,
    BridgeStateEvent.RUNNING,
    BridgeStateEvent.CONNECTING,
    BridgeStateEvent.CONNECTED,
    BridgeStateEvent.BACKFILLING,
)


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
    info: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None

    send_attempts_: int = field(default=0, hidden=True)

    def fill(self) -> "BridgeState":
        self.timestamp = self.timestamp or int(time.time())
        self.source = self.source or self.default_source
        if not self.ttl:
            self.ttl = (
                self.default_ok_ttl
                if self.state_event in ok_ish_states
                else self.default_error_ttl
            )
        if self.error:
            try:
                msg = self.human_readable_errors[self.error]
            except KeyError:
                pass
            else:
                self.message = msg.format(message=self.message) if self.message else msg
        return self

    def should_deduplicate(self, prev_state: Optional["BridgeState"]) -> bool:
        if (
            not prev_state
            or prev_state.state_event != self.state_event
            or prev_state.error != self.error
            or prev_state.info != self.info
        ):
            # If there's no previous state or the state was different, send this one.
            return False
        # If there's more than ⅘ of the previous pong's time-to-live left, drop this one
        return prev_state.timestamp + (prev_state.ttl / 5) > self.timestamp

    async def send(self, url: str, token: str, log: logging.Logger, log_sent: bool = True) -> bool:
        if not url:
            return True
        self.send_attempts_ += 1
        headers = {"Authorization": f"Bearer {token}", "User-Agent": HTTPAPI.default_ua}
        try:
            async with aiohttp.ClientSession() as sess, sess.post(
                url, json=self.serialize(), headers=headers
            ) as resp:
                if not 200 <= resp.status < 300:
                    text = await resp.text()
                    text = text.replace("\n", "\\n")
                    log.warning(
                        f"Unexpected status code {resp.status} "
                        f"sending bridge state update: {text}"
                    )
                    return False
                elif log_sent:
                    log.debug(f"Sent new bridge state {self}")
        except Exception as e:
            log.warning(f"Failed to send updated bridge state: {e}")
            return False
        return True


@dataclass(kw_only=True)
class GlobalBridgeState(SerializableAttrs):
    remote_states: Optional[Dict[str, BridgeState]] = field(json="remoteState", default=None)
    bridge_state: BridgeState = field(json="bridgeState")
