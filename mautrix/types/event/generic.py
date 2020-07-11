# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, NewType

from ..primitive import JSON
from ..util import deserializer, Obj
from .base import EventType, GenericEvent
from .redaction import RedactionEvent, RedactionEventContent
from .message import MessageEvent, MessageEventContent
from .reaction import ReactionEvent, ReactionEventContent
from .encrypted import EncryptedEvent, EncryptedEventContent
from .state import StateEvent, StateEventContent
from .account_data import AccountDataEvent, AccountDataEventContent
from .to_device import ToDeviceEvent, ToDeviceEventContent
from .ephemeral import (ReceiptEvent, PresenceEvent, TypingEvent, ReceiptEventContent,
                        TypingEventContent, EphemeralEvent)

Event = NewType("Event", Union[MessageEvent, ReactionEvent, RedactionEvent, StateEvent, TypingEvent,
                               ReceiptEvent, PresenceEvent, EncryptedEvent, ToDeviceEvent,
                               GenericEvent])

EventContent = Union[MessageEventContent, RedactionEventContent, ReactionEventContent,
                     StateEventContent, AccountDataEventContent, ReceiptEventContent,
                     TypingEventContent, EncryptedEventContent, ToDeviceEventContent, Obj]


@deserializer(Event)
def deserialize_event(data: JSON) -> Event:
    event_type = EventType.find(data.get("type", None))
    if event_type == EventType.ROOM_MESSAGE:
        return MessageEvent.deserialize(data)
    elif event_type == EventType.STICKER:
        data.get("content", {})["msgtype"] = "m.sticker"
        return MessageEvent.deserialize(data)
    elif event_type == EventType.REACTION:
        return ReactionEvent.deserialize(data)
    elif event_type == EventType.ROOM_REDACTION:
        return RedactionEvent.deserialize(data)
    elif event_type == EventType.ROOM_ENCRYPTED:
        return EncryptedEvent.deserialize(data)
    elif event_type.is_to_device:
        return ToDeviceEvent.deserialize(data)
    elif event_type.is_state:
        return StateEvent.deserialize(data)
    elif event_type.is_account_data:
        return AccountDataEvent.deserialize(data)
    elif event_type.is_ephemeral:
        return EphemeralEvent.deserialize(data)
    else:
        return GenericEvent.deserialize(data)


setattr(Event, "deserialize", deserialize_event)
