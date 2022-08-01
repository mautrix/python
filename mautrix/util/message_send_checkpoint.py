# Copyright (c) 2022 Sumner Evans
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
import logging

from aiohttp.client import ClientTimeout
from attr import dataclass
import aiohttp

from mautrix.api import HTTPAPI
from mautrix.types import EventType, MessageType, SerializableAttrs, SerializableEnum


class MessageSendCheckpointStep(SerializableEnum):
    CLIENT = "CLIENT"
    HOMESERVER = "HOMESERVER"
    BRIDGE = "BRIDGE"
    DECRYPTED = "DECRYPTED"
    REMOTE = "REMOTE"
    COMMAND = "COMMAND"


class MessageSendCheckpointStatus(SerializableEnum):
    SUCCESS = "SUCCESS"
    WILL_RETRY = "WILL_RETRY"
    PERM_FAILURE = "PERM_FAILURE"
    UNSUPPORTED = "UNSUPPORTED"
    TIMEOUT = "TIMEOUT"


class MessageSendCheckpointReportedBy(SerializableEnum):
    ASMUX = "ASMUX"
    BRIDGE = "BRIDGE"


@dataclass
class MessageSendCheckpoint(SerializableAttrs):
    event_id: str
    room_id: str
    step: MessageSendCheckpointStep
    timestamp: int
    status: MessageSendCheckpointStatus
    event_type: EventType
    reported_by: MessageSendCheckpointReportedBy
    retry_num: int = 0
    message_type: Optional[MessageType] = None
    info: Optional[str] = None
    client_type: Optional[str] = None
    client_version: Optional[str] = None

    async def send(self, endpoint: str, as_token: str, log: logging.Logger) -> None:
        if not endpoint:
            return
        try:
            headers = {"Authorization": f"Bearer {as_token}", "User-Agent": HTTPAPI.default_ua}
            async with aiohttp.ClientSession() as sess, sess.post(
                endpoint,
                json={"checkpoints": [self.serialize()]},
                headers=headers,
                timeout=ClientTimeout(30),
            ) as resp:
                if not 200 <= resp.status < 300:
                    text = await resp.text()
                    text = text.replace("\n", "\\n")
                    log.warning(
                        f"Unexpected status code {resp.status} sending checkpoint "
                        f"for {self.event_id} ({self.step}/{self.status}): {text}"
                    )
                else:
                    log.info(
                        f"Successfully sent checkpoint for {self.event_id} "
                        f"({self.step}/{self.status})"
                    )
        except Exception as e:
            log.warning(
                f"Failed to send checkpoint for {self.event_id} ({self.step}/{self.status}): "
                f"{type(e).__name__}: {e}"
            )


CHECKPOINT_TYPES = {
    EventType.ROOM_REDACTION,
    EventType.ROOM_MESSAGE,
    EventType.ROOM_ENCRYPTED,
    EventType.ROOM_MEMBER,
    EventType.ROOM_NAME,
    EventType.ROOM_AVATAR,
    EventType.ROOM_TOPIC,
    EventType.STICKER,
    EventType.REACTION,
    EventType.CALL_INVITE,
    EventType.CALL_CANDIDATES,
    EventType.CALL_SELECT_ANSWER,
    EventType.CALL_ANSWER,
    EventType.CALL_HANGUP,
    EventType.CALL_REJECT,
    EventType.CALL_NEGOTIATE,
}
