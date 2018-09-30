from typing import Optional
import attr

from ..util import SerializableEnum, SerializableAttrs
from .base import BaseRoomEvent, BaseUnsigned


class Format(SerializableEnum):
    HTML = "org.matrix.custom.html"


class MessageType(SerializableEnum):
    TEXT = "m.text"
    EMOTE = "m.emote"
    NOTICE = "m.notice"
    IMAGE = "m.image"
    VIDEO = "m.video"
    AUDIO = "m.audio"
    FILE = "m.file"
    LOCATION = "m.location"


@attr.s(auto_attribs=True)
class InReplyTo(SerializableAttrs['InReplyTo']):
    event_id: str = None


@attr.s(auto_attribs=True)
class RelatesTo(SerializableAttrs['RelatesTo']):
    in_reply_to: InReplyTo = attr.ib(default=None, metadata={"json": "m.in_reply_to"})


@attr.s(auto_attribs=True)
class MatchedCommand(SerializableAttrs['MatchedCommand']):
    pass


@attr.s(auto_attribs=True)
class BaseFileInfo(SerializableAttrs['BaseFileInfo']):
    mimetype: str = None
    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    duration: int = None
    size: int = None


@attr.s(auto_attribs=True)
class FileInfo(BaseFileInfo, SerializableAttrs['FileInfo']):
    thumbnail_info: BaseFileInfo = None
    thumbnail_url: str = None


@attr.s(auto_attribs=True)
class MessageEventContent(SerializableAttrs['EventContent']):
    msgtype: MessageType = None
    body: str = None
    format: Format = None
    formatted_body: str = None

    url: str = None
    info: FileInfo = None

    redaction_reason: str = attr.ib(default=None, metadata={"json": "reason"})

    relates_to: RelatesTo = attr.ib(default=None, metadata={"json": "m.relates_to"})
    command: MatchedCommand = attr.ib(default=None, metadata={"json": "m.command"})


@attr.s(auto_attribs=True)
class MessageUnsigned(BaseUnsigned, SerializableAttrs['MessageUnsigned']):
    transaction_id: str = None


@attr.s(auto_attribs=True)
class MessageEvent(BaseRoomEvent, SerializableAttrs['Event']):
    content: MessageEventContent
    redacts: str = None
    unsigned: Optional[MessageUnsigned] = None
