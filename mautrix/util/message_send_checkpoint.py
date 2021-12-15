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

    async def send(self, log: logging.Logger, endpoint: str, as_token: str) -> None:
        if not endpoint:
            return
        try:
            headers = {"Authorization": f"Bearer {as_token}", "User-Agent": HTTPAPI.default_ua}
            async with aiohttp.ClientSession() as sess, sess.post(
                endpoint,
                json={"checkpoints": [self.serialize()]},
                headers=headers,
                timeout=ClientTimeout(5),
            ) as resp:
                if not 200 <= resp.status < 300:
                    text = await resp.text()
                    text = text.replace("\n", "\\n")
                    log.warning(
                        f"Unexpected status code {resp.status} sending message send checkpoints "
                        f"for {self.event_id}: {text}"
                    )
                else:
                    log.info(
                        f"Successfully sent message send checkpoints for {self.event_id} "
                        f"(step: {self.step})"
                    )
        except Exception as e:
            log.warning(f"Failed to send message send checkpoints for {self.event_id}: {e}")


CHECKPOINT_TYPES = {
    EventType.ROOM_REDACTION,
    EventType.ROOM_MESSAGE,
    EventType.ROOM_ENCRYPTED,
    EventType.ROOM_MEMBER,
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
