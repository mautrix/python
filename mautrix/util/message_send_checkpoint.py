from typing import Optional
from attr import dataclass
from mautrix.types.util.serializable import SerializableEnum
from mautrix.types.util.serializable_attrs import SerializableAttrs


class MessageSendCheckpointStep(SerializableEnum):
    CLIENT = "CLIENT"
    HOMESERVER = "HOMESERVER"
    BRIDGE = "BRIDGE"
    REMOTE = "REMOTE"


class MessageSendCheckpointStatus(SerializableEnum):
    SUCCESS = "SUCCESS"
    WILL_RETRY = "WILL_RETRY"
    PERM_FAILURE = "PERM_FAILURE"


class MessageSendCheckpointReportedBy(SerializableEnum):
    ASMUX = "ASMUX"
    BRIDGE = "BRIDGE"


@dataclass
class MessageSendCheckpoint(SerializableAttrs):
    event_id: str
    room_id: str
    username: str
    step: MessageSendCheckpointStep
    bridge: str
    timestamp: int
    status: MessageSendCheckpointStatus
    event_type: str
    reported_by: MessageSendCheckpointReportedBy
    retry_num: int = 0
    info: Optional[str] = None
