# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional

from attr import dataclass

from ..primitive import EventID
from ..util import SerializableAttrs, SerializableEnum, field
from .base import BaseRoomEvent
from .message import RelatesTo


class MessageStatusReason(SerializableEnum):
    GENERIC_ERROR = "m.event_not_handled"
    UNSUPPORTED = "com.beeper.unsupported_event"
    UNDECRYPTABLE = "com.beeper.undecryptable_event"
    TOO_OLD = "m.event_too_old"
    NETWORK_ERROR = "m.foreign_network_error"
    NO_PERMISSION = "m.no_permission"

    @property
    def checkpoint_status(self):
        from mautrix.util.message_send_checkpoint import MessageSendCheckpointStatus

        if self == MessageStatusReason.UNSUPPORTED:
            return MessageSendCheckpointStatus.UNSUPPORTED
        elif self == MessageStatusReason.TOO_OLD:
            return MessageSendCheckpointStatus.TIMEOUT
        return MessageSendCheckpointStatus.PERM_FAILURE


class MessageStatus(SerializableEnum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    RETRIABLE = "FAIL_RETRIABLE"
    FAIL = "FAIL_PERMANENT"


@dataclass(kw_only=True)
class BeeperMessageStatusEventContent(SerializableAttrs):
    relates_to: RelatesTo = field(json="m.relates_to")
    network: str = ""
    status: Optional[MessageStatus] = None

    reason: Optional[MessageStatusReason] = None
    error: Optional[str] = None
    message: Optional[str] = None

    success: Optional[bool] = None
    still_working: Optional[bool] = None
    can_retry: Optional[bool] = None
    is_certain: Optional[bool] = None

    last_retry: Optional[EventID] = None

    def fill_legacy_booleans(self) -> None:
        self.success = self.status == MessageStatus.SUCCESS
        if not self.success:
            self.still_working = self.status == MessageStatus.PENDING
            self.can_retry = self.status in (MessageStatus.PENDING, MessageStatus.RETRIABLE)


@dataclass
class BeeperMessageStatusEvent(BaseRoomEvent, SerializableAttrs):
    content: BeeperMessageStatusEventContent
