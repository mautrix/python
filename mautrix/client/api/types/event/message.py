from typing import Optional, Union, Dict, List
from attr import dataclass
import attr

from .....api import JSON
from ..util import SerializableEnum, SerializableAttrs, Obj, deserializer
from ..primitive import ContentURI, EventID, UserID
from .base import BaseRoomEvent, BaseUnsigned


class Format(SerializableEnum):
    """A message format. Currently only ``org.matrix.custom.html`` is available.
    This will probably be deprecated when extensible events are implemented."""
    HTML = "org.matrix.custom.html"


TEXT_MESSAGE_TYPES = ("m.text", "m.emote", "m.notice")
MEDIA_MESSAGE_TYPES = ("m.image", "m.video", "m.audio", "m.file")


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


@dataclass
class InReplyTo(SerializableAttrs['InReplyTo']):
    """Message reply info. Currently only contains the ID of the event that an event is replying to.
    Cross-room replies are not possible, as other users may not be able to view events in the other
    room."""
    event_id: EventID = None


@dataclass
class RelatesTo(SerializableAttrs['RelatesTo']):
    """Message relations. Currently only used for replies, but will be used for reactions, edits,
    threading, etc in the future."""
    in_reply_to: InReplyTo = attr.ib(default=None, metadata={"json": "m.in_reply_to"})


@dataclass
class MatchedCommand(SerializableAttrs['MatchedCommand']):
    target: UserID = None
    matched: str = None
    arguments: Dict[str, str] = None


@dataclass
class MatchedPassiveCommand(SerializableAttrs['MatchedPassiveCommand']):
    captured: List[List[str]] = None

    command: str = None
    arguments: Dict[str, str] = None


@dataclass
class BaseMessageEventContent:
    msgtype: MessageType
    body: str


@dataclass
class TextMessageEventContent(BaseMessageEventContent,
                              SerializableAttrs['TextMessageEventContent']):
    format: Format = None
    formatted_body: str = None

    command: MatchedCommand = attr.ib(default=None, metadata={"json": "m.command"})
    relates_to: RelatesTo = attr.ib(default=None, metadata={"json": "m.relates_to"})


@dataclass
class ThumbnailInfo(SerializableAttrs['ThumbnailInfo']):
    """Information about the thumbnail for a document, video, image or location."""
    mimetype: str = None
    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    size: int = None


@dataclass
class ImageInfo(SerializableAttrs['ImageInfo']):
    """Information about an image message."""
    mimetype: str = None
    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    size: int = None
    thumbnail_info: ThumbnailInfo = None
    thumbnail_url: ContentURI = None


@dataclass
class VideoInfo(SerializableAttrs['VideoInfo']):
    """Information about a video message."""
    mimetype: str = None
    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    size: int = None
    duration: int = None
    thumbnail_info: ThumbnailInfo = None
    thumbnail_url: ContentURI = None


@dataclass
class AudioInfo(SerializableAttrs['AudioInfo']):
    """Information about an audio message."""
    mimetype: str = None
    size: int = None
    duration: int = None


@dataclass
class FileInfo(SerializableAttrs['FileInfo']):
    """Information about a document message."""
    mimetype: str = None
    size: int = None
    thumbnail_info: ThumbnailInfo = None
    thumbnail_url: ContentURI = None


MediaInfo = Union[ImageInfo, VideoInfo, AudioInfo, FileInfo, Obj]


@dataclass
class MediaMessageEventContent(BaseMessageEventContent,
                               SerializableAttrs['MediaMessageEventContent']):
    url: ContentURI
    info: MediaInfo = None

    relates_to: RelatesTo = attr.ib(default=None, metadata={"json": "m.relates_to"})

    @staticmethod
    @deserializer(MediaInfo)
    def deserialize_info(data: JSON) -> MediaInfo:
        if not isinstance(data, dict):
            return Obj()
        msgtype = data.pop("__mautrix_msgtype", None)
        if msgtype == "m.image":
            return ImageInfo.deserialize(data)
        elif msgtype == "m.video":
            return VideoInfo.deserialize(data)
        elif msgtype == "m.audio":
            return AudioInfo.deserialize(data)
        elif msgtype == "m.file":
            return FileInfo.deserialize(data)
        else:
            return Obj(**data)


@dataclass
class LocationInfo(SerializableAttrs['LocationInfo']):
    """Information about a location message."""
    thumbnail_url: ContentURI = None
    thumbnail_info: ThumbnailInfo = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    duration: int = None
    size: int = None


@dataclass
class LocationMessageEventContent(BaseMessageEventContent,
                                  SerializableAttrs['LocationMessageEventContent']):
    geo_uri: str
    info: LocationInfo = None

    relates_to: RelatesTo = attr.ib(default=None, metadata={"json": "m.relates_to"})


@dataclass
class MessageUnsigned(BaseUnsigned, SerializableAttrs['MessageUnsigned']):
    """Unsigned information sent with message events."""
    transaction_id: str = None
    passive_command: MatchedPassiveCommand = attr.ib(default=None,
                                                     metadata={"json": "m.passive_command"})


MessageEventContent = Union[TextMessageEventContent, MediaMessageEventContent,
                            LocationMessageEventContent, Obj]


@dataclass
class MessageEvent(BaseRoomEvent, SerializableAttrs['MessageEvent']):
    """A m.room.message event"""
    content: MessageEventContent
    unsigned: Optional[MessageUnsigned] = None

    @staticmethod
    @deserializer(MessageEventContent)
    def deserialize_content(data: JSON) -> MessageEventContent:
        if not isinstance(data, dict):
            return Obj()
        msgtype = data.get("msgtype", None)
        if msgtype in TEXT_MESSAGE_TYPES:
            return TextMessageEventContent.deserialize(data)
        elif msgtype in MEDIA_MESSAGE_TYPES:
            data.get("info", {})["__mautrix_msgtype"] = msgtype
            return MediaMessageEventContent.deserialize(data)
        elif msgtype == "m.location":
            return LocationMessageEventContent.deserialize(data)
        else:
            return Obj(**data)


@dataclass
class StickerEventContent(SerializableAttrs['StickerEventContent']):
    body: str
    url: ContentURI
    info: ImageInfo = None

    relates_to: RelatesTo = attr.ib(default=None, metadata={"json": "m.relates_to"})


@dataclass
class StickerEvent(BaseRoomEvent, SerializableAttrs['StickerEvent']):
    """A m.sticker event"""
    content: StickerEventContent
    unsigned: Optional[MessageUnsigned] = None


@dataclass
class RedactionEventContent(SerializableAttrs['RedactionEventContent']):
    reason: str = None


@dataclass
class RedactionEvent(BaseRoomEvent, SerializableAttrs['RedactionEvent']):
    """A m.room.redaction event"""
    content: StickerEventContent
    redacts: str
    unsigned: Optional[MessageUnsigned] = None
