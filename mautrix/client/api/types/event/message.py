# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Union, Pattern
from html import escape
import warnings
import re

from attr import dataclass
import attr

from .....api import JSON
from ..util import SerializableEnum, SerializableAttrs, Serializable, Obj, deserializer, serializer
from ..primitive import ContentURI, EventID
from .base import BaseRoomEvent, BaseUnsigned


# region Message types

class Format(SerializableEnum):
    """A message format. Currently only ``org.matrix.custom.html`` is available.
    This will probably be deprecated when extensible events are implemented."""
    HTML = "org.matrix.custom.html"


TEXT_MESSAGE_TYPES = ("m.text", "m.emote", "m.notice")
MEDIA_MESSAGE_TYPES = ("m.image", "m.sticker", "m.video", "m.audio", "m.file")


class MessageType(SerializableEnum):
    """A message type."""
    TEXT = "m.text"
    EMOTE = "m.emote"
    NOTICE = "m.notice"
    IMAGE = "m.image"
    STICKER = "m.sticker"
    VIDEO = "m.video"
    AUDIO = "m.audio"
    FILE = "m.file"
    LOCATION = "m.location"

    @property
    def is_text(self) -> bool:
        return self.value in TEXT_MESSAGE_TYPES

    @property
    def is_media(self) -> bool:
        return self.value in MEDIA_MESSAGE_TYPES


# endregion
# region Relations

class InReplyTo:
    def __init__(self, event_id: Optional[EventID] = None,
                 proxy_target: Optional['RelatesTo'] = None) -> None:
        self._event_id = event_id
        self._proxy_target = proxy_target

    @property
    def event_id(self) -> EventID:
        if self._proxy_target:
            return self._proxy_target.event_id
        return self._event_id

    @event_id.setter
    def event_id(self, event_id: EventID) -> None:
        if self._proxy_target:
            self._proxy_target.rel_type = RelationType.REFERENCE
            self._proxy_target.event_id = event_id
        else:
            self._event_id = event_id


class RelationType(SerializableEnum):
    ANNOTATION = "m.annotation"
    REFERENCE = "m.reference"
    REPLACE = "m.replace"


@dataclass
class RelatesTo(Serializable):
    """Message relations. Used for reactions, edits and replies."""
    rel_type: RelationType = None
    event_id: Optional[EventID] = None
    key: Optional[str] = None

    @classmethod
    def deserialize(cls, data: JSON) -> Optional['RelatesTo']:
        if not data:
            return None
        try:
            return cls(rel_type=RelationType.deserialize(data["rel_type"]),
                       event_id=data.get("event_id", None), key=data.get("key", None))
        except KeyError:
            pass
        try:
            return cls(rel_type=RelationType.REFERENCE, event_id=data["m.in_reply_to"]["event_id"])
        except KeyError:
            pass
        return None

    def serialize(self) -> JSON:
        data = {
            "rel_type": self.rel_type.serialize(),
        }
        if self.rel_type == RelationType.REFERENCE:
            data["m.in_reply_to"] = {
                "event_id": self.event_id
            }
        if self.event_id:
            data["event_id"] = self.event_id
        if self.key:
            data["key"] = self.key
        return data

    @property
    def in_reply_to(self) -> InReplyTo:
        warnings.warn("m.in_reply_to is deprecated. Use rel_type=RelationType.REFERENCE and "
                      "event_id instead", category=DeprecationWarning)
        if self.rel_type == RelationType.REFERENCE:
            return InReplyTo(proxy_target=self)
        return InReplyTo()

    @in_reply_to.setter
    def in_reply_to(self, in_reply_to: InReplyTo) -> None:
        warnings.warn("m.in_reply_to is deprecated. Use rel_type=RelationType.REFERENCE and "
                      "event_id instead", category=DeprecationWarning)
        self.rel_type = RelationType.REFERENCE
        self.event_id = in_reply_to.event_id
        in_reply_to._proxy_target = self


# endregion
# region Base event content

class BaseMessageEventContentFuncs:
    """Base class for the contents of all message-type events (currently m.room.message and
    m.sticker). Contains relation helpers."""
    body: str
    _relates_to: Optional[RelatesTo]

    def set_reply(self, in_reply_to: 'MessageEvent') -> None:
        self.relates_to.rel_type = RelationType.REFERENCE
        self.relates_to.event_id = in_reply_to.event_id

    def set_edit(self, edits: 'MessageEvent') -> None:
        self.relates_to.rel_type = RelationType.REPLACE
        self.relates_to.event_id = edits.event_id

    @property
    def relates_to(self) -> RelatesTo:
        if self._relates_to is None:
            self._relates_to = RelatesTo()
        return self._relates_to

    @relates_to.setter
    def relates_to(self, relates_to: RelatesTo) -> None:
        self._relates_to = relates_to

    def get_reply_to(self) -> Optional[EventID]:
        if self._relates_to and self._relates_to.rel_type == RelationType.REFERENCE:
            return self._relates_to.event_id
        return None

    def get_edit(self) -> Optional[EventID]:
        if self._relates_to and self._relates_to.rel_type == RelationType.REPLACE:
            return self._relates_to.event_id
        return None

    def trim_reply_fallback(self) -> None:
        pass


@dataclass
class BaseMessageEventContent(BaseMessageEventContentFuncs):
    """Base event content for all m.room.message-type events."""
    msgtype: MessageType = None
    body: str = ""


# endregion
# region Media info

@dataclass
class BaseFileInfo(SerializableAttrs['BaseFileInfo']):
    mimetype: str = None
    size: int = None


@dataclass
class ThumbnailInfo(BaseFileInfo, SerializableAttrs['ThumbnailInfo']):
    """Information about the thumbnail for a document, video, image or location."""
    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})


@dataclass
class FileInfo(BaseFileInfo, SerializableAttrs['FileInfo']):
    """Information about a document message."""
    thumbnail_info: ThumbnailInfo = None
    thumbnail_url: ContentURI = None


@dataclass
class ImageInfo(FileInfo, SerializableAttrs['ImageInfo']):
    """Information about an image message."""
    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})


@dataclass
class VideoInfo(ImageInfo, SerializableAttrs['VideoInfo']):
    """Information about a video message."""
    duration: int = None


@dataclass
class AudioInfo(BaseFileInfo, SerializableAttrs['AudioInfo']):
    """Information about an audio message."""
    duration: int = None


MediaInfo = Union[ImageInfo, VideoInfo, AudioInfo, FileInfo, Obj]


@dataclass
class LocationInfo(SerializableAttrs['LocationInfo']):
    """Information about a location message."""
    thumbnail_url: ContentURI = None
    thumbnail_info: ThumbnailInfo = None


# endregion
# region Event content

@dataclass
class MediaMessageEventContent(BaseMessageEventContent,
                               SerializableAttrs['MediaMessageEventContent']):
    """The content of a media message event (m.image, m.audio, m.video, m.file)"""
    url: ContentURI = None
    info: Optional[MediaInfo] = None

    _relates_to: Optional[RelatesTo] = attr.ib(default=None, metadata={"json": "m.relates_to"})

    @staticmethod
    @deserializer(MediaInfo)
    def deserialize_info(data: JSON) -> MediaInfo:
        if not isinstance(data, dict):
            return Obj()
        msgtype = data.pop("__mautrix_msgtype", None)
        if msgtype == "m.image" or msgtype == "m.sticker":
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
class LocationMessageEventContent(BaseMessageEventContent,
                                  SerializableAttrs['LocationMessageEventContent']):
    geo_uri: str = None
    info: LocationInfo = None

    _relates_to: Optional[RelatesTo] = attr.ib(default=None, metadata={"json": "m.relates_to"})


html_reply_fallback_regex: Pattern = re.compile("^<mx-reply>"
                                                r"[\s\S]+?"
                                                "</mx-reply>")


@dataclass
class TextMessageEventContent(BaseMessageEventContent,
                              SerializableAttrs['TextMessageEventContent']):
    """The content of a text message event (m.text, m.notice, m.emote)"""
    format: Format = None
    formatted_body: str = None

    _relates_to: Optional[RelatesTo] = attr.ib(default=None, metadata={"json": "m.relates_to"})

    def set_reply(self, in_reply_to: 'MessageEvent') -> None:
        super().set_reply(in_reply_to)
        if not self.formatted_body or len(self.formatted_body) == 0 or self.format != Format.HTML:
            self.format = Format.HTML
            self.formatted_body = escape(self.body)
        self.formatted_body = in_reply_to.make_reply_fallback_html() + self.formatted_body
        self.body = in_reply_to.make_reply_fallback_text() + self.body

    def trim_reply_fallback(self) -> None:
        if self.get_reply_to():
            self._trim_reply_fallback_text()
            self._trim_reply_fallback_html()

    def _trim_reply_fallback_text(self) -> None:
        if not self.body.startswith("> ") or "\n" not in self.body:
            return
        lines = self.body.split("\n")
        while len(lines) > 0 and lines[0].startswith("> "):
            lines.pop(0)
        # Pop extra newline at end of fallback
        lines.pop(0)
        self.body = "\n".join(lines)

    def _trim_reply_fallback_html(self) -> None:
        if self.formatted_body and self.format == Format.HTML:
            self.formatted_body = html_reply_fallback_regex.sub("", self.formatted_body)


MessageEventContent = Union[TextMessageEventContent, MediaMessageEventContent,
                            LocationMessageEventContent, Obj]


# endregion

@dataclass
class MessageUnsigned(BaseUnsigned, SerializableAttrs['MessageUnsigned']):
    """Unsigned information sent with message events."""
    transaction_id: str = None


html_reply_fallback_format = ("<mx-reply><blockquote>"
                              "<a href='https://matrix.to/#/{room_id}/{event_id}'>In reply to</a>"
                              "<a href='https://matrix.to/#/{sender}'>{displayname}</a>"
                              "{content}"
                              "</blockquote></mx-reply>")

media_reply_fallback_body_map = {
    MessageType.IMAGE: "an image",
    MessageType.STICKER: "a sticker",
    MessageType.AUDIO: "audio",
    MessageType.VIDEO: "a video",
    MessageType.FILE: "a file",
    MessageType.LOCATION: "a location",
}


@dataclass
class MessageEvent(BaseRoomEvent, SerializableAttrs['MessageEvent']):
    """An m.room.message event"""
    content: MessageEventContent
    unsigned: Optional[MessageUnsigned] = None

    @staticmethod
    @deserializer(MessageEventContent)
    def deserialize_content(data: JSON) -> MessageEventContent:
        if not isinstance(data, dict):
            return Obj()
        rel = (data.get("m.relates_to", None) or {})
        if rel.get("rel_type", None) == RelationType.REPLACE.value:
            data = data.get("m.new_content", data)
            data["m.relates_to"] = rel
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

    @staticmethod
    @serializer(MessageEventContent)
    def serialize_content(content: MessageEventContent) -> JSON:
        data = content.serialize()
        evt = content.get_edit()
        if evt:
            new_content = {**data}
            del new_content["m.relates_to"]
            data["m.new_content"] = new_content
            if "body" in data:
                data["body"] = f"* {data['body']}"
            if "formatted_body" in data:
                data["formatted_body"] = f"* {data['formatted_body']}"
        return data

    def make_reply_fallback_html(self) -> str:
        """Generate the HTML fallback for messages replying to this event."""
        if self.content.msgtype.is_text:
            body = self.content.formatted_body or escape(self.content.body)
        else:
            sent_type = media_reply_fallback_body_map[self.content.msgtype] or "a message"
            body = f"sent {sent_type}"
        displayname = self.sender
        return html_reply_fallback_format.format(room_id=self.room_id, event_id=self.event_id,
                                                 sender=self.sender, displayname=displayname,
                                                 content=body)

    def make_reply_fallback_text(self) -> str:
        """Generate the plaintext fallback for messages replying to this event."""
        if self.content.msgtype.is_text:
            body = self.content.body
        else:
            body = media_reply_fallback_body_map[self.content.msgtype]
        lines = body.strip().split("\n")
        first_line, lines = lines[0], lines[1:]
        displayname = self.sender
        fallback_text = f"> <{displayname}> {first_line}"
        for line in lines:
            fallback_text += f"\n> {line}"
        fallback_text += "\n\n"
        return fallback_text
