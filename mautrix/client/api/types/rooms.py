from enum import Enum
from typing import List
import attr

from .primitive import RoomID
from mautrix.client.api.types.util.serializable import SerializableAttrs


class RoomCreatePreset(Enum):
    PRIVATE = "private_chat"
    TRUSTED_PRIVATE = "trusted_private_chat"
    PUBLIC = "public_chat"


class RoomCreateVisibility(Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class PaginationDirection(Enum):
    FORWARD = "f"
    BACKWARD = "b"


@attr.s(auto_attribs=True)
class RoomAliasInfo(SerializableAttrs['RoomAliasInfo']):
    room_id: RoomID = None
    servers: List[str] = None
