# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Generic, List, Optional, TypeVar, Union

from attr import dataclass
import attr

from ..primitive import JSON, UserID
from ..util import ExtensibleEnum, SerializableAttrs
from .base import BaseRoomEvent
from .type import EventType


class CallDataType(ExtensibleEnum):
    OFFER = "offer"
    ANSWER = "answer"


class CallHangupReason(ExtensibleEnum):
    ICE_FAILED = "ice_failed"
    INVITE_TIMEOUT = "invite_timeout"
    USER_HANGUP = "user_hangup"
    USER_MEDIA_FAILED = "user_media_failed"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class CallData(SerializableAttrs):
    sdp: str
    type: CallDataType


@dataclass
class CallCandidate(SerializableAttrs):
    candidate: str
    sdp_m_line_index: int = attr.ib(metadata={"json": "sdpMLineIndex"}, default=None)
    sdp_mid: str = attr.ib(metadata={"json": "sdpMid"}, default=None)


@dataclass
class CallInviteEventContent(SerializableAttrs):
    call_id: str
    lifetime: int
    version: int
    offer: CallData
    party_id: Optional[str] = None
    invitee: Optional[UserID] = None


@dataclass
class CallCandidatesEventContent(SerializableAttrs):
    call_id: str
    version: int
    candidates: List[CallCandidate]
    party_id: Optional[str] = None


@dataclass
class CallSelectAnswerEventContent(SerializableAttrs):
    call_id: str
    version: int
    party_id: str
    selected_party_id: str


@dataclass
class CallAnswerEventContent(SerializableAttrs):
    call_id: str
    version: int
    answer: CallData
    party_id: Optional[str] = None


@dataclass
class CallHangupEventContent(SerializableAttrs):
    call_id: str
    version: int
    reason: CallHangupReason = CallHangupReason.USER_HANGUP
    party_id: Optional[str] = None


@dataclass
class CallRejectEventContent(SerializableAttrs):
    call_id: str
    version: int
    party_id: str


@dataclass
class CallNegotiateEventContent(SerializableAttrs):
    call_id: str
    version: int
    lifetime: int
    party_id: str
    description: CallData


type_to_class = {
    EventType.CALL_INVITE: CallInviteEventContent,
    EventType.CALL_CANDIDATES: CallCandidatesEventContent,
    EventType.CALL_SELECT_ANSWER: CallSelectAnswerEventContent,
    EventType.CALL_ANSWER: CallAnswerEventContent,
    EventType.CALL_HANGUP: CallHangupEventContent,
    EventType.CALL_NEGOTIATE: CallNegotiateEventContent,
    EventType.CALL_REJECT: CallRejectEventContent,
}

CallEventContent = Union[
    CallInviteEventContent,
    CallCandidatesEventContent,
    CallAnswerEventContent,
    CallSelectAnswerEventContent,
    CallHangupEventContent,
    CallNegotiateEventContent,
    CallRejectEventContent,
]

T = TypeVar("T", bound=CallEventContent)


@dataclass
class CallEvent(BaseRoomEvent, SerializableAttrs, Generic[T]):
    content: T

    @classmethod
    def deserialize(cls, data: JSON, event_type: Optional[EventType] = None) -> "CallEvent":
        event_type = event_type or EventType.find(data.get("type"))
        data["content"] = type_to_class[event_type].deserialize(data["content"])
        return super().deserialize(data)
