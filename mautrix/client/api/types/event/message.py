from typing import Optional
import attr

from ..util import SerializableEnum, SerializableAttrs
from .base import BaseRoomEvent, BaseUnsigned


class Format(SerializableEnum):
    """A message format. Currently only ``org.matrix.custom.html`` is available.
    This will probably be deprecated when extensible events are implemented."""
    HTML = "org.matrix.custom.html"


class MessageType(SerializableEnum):
    """A message type."""
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
    """Message reply info. Currently only contains the ID of the event that an event is replying to.
    Cross-room replies are not possible, as other users may not be able to view events in the other
    room."""
    event_id: str = None


@attr.s(auto_attribs=True)
class RelatesTo(SerializableAttrs['RelatesTo']):
    """Message relations. Currently only used for replies, but will be used for reactions, edits,
    threading, etc in the future."""
    in_reply_to: InReplyTo = attr.ib(default=None, metadata={"json": "m.in_reply_to"})


@attr.s(auto_attribs=True)
class MatchedCommand(SerializableAttrs['MatchedCommand']):
    pass


@attr.s(auto_attribs=True)
class BaseFileInfo(SerializableAttrs['BaseFileInfo']):
    """Basic information about a file (no thumbnail)."""
    mimetype: str = None
    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    duration: int = None
    size: int = None


@attr.s(auto_attribs=True)
class FileInfo(BaseFileInfo, SerializableAttrs['FileInfo']):
    """Information about a file and possibly a thumbnail of the image/video/etc."""
    thumbnail_info: BaseFileInfo = None
    thumbnail_url: str = None


@attr.s(auto_attribs=True)
class MessageEventContent(SerializableAttrs['EventContent']):
    """The content of a message event. The contents of all known different message event types are
    available in this object. Most event types have at least a `msgtype` and a `body`, but you
    should still check the :MessageEvent:`type` beforehand."""
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
    """Unsigned information sent with message events."""
    transaction_id: str = None


@attr.s(auto_attribs=True)
class MessageEvent(BaseRoomEvent, SerializableAttrs['Event']):
    """A room message event."""
    content: MessageEventContent
    redacts: str = None
    unsigned: Optional[MessageUnsigned] = None
