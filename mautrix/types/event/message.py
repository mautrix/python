# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Optional, Pattern, Union
from html import escape
import re

from attr import dataclass
import attr

from ..primitive import JSON, ContentURI, EventID
from ..util import ExtensibleEnum, Obj, SerializableAttrs, deserializer, field
from .base import BaseRoomEvent, BaseUnsigned

# region Message types


class Format(ExtensibleEnum):
    """A message format. Currently only ``org.matrix.custom.html`` is available.
    This will probably be deprecated when extensible events are implemented."""

    HTML: "Format" = "org.matrix.custom.html"


TEXT_MESSAGE_TYPES = ("m.text", "m.emote", "m.notice")
MEDIA_MESSAGE_TYPES = ("m.image", "m.sticker", "m.video", "m.audio", "m.file")


class MessageType(ExtensibleEnum):
    """A message type."""

    TEXT: "MessageType" = "m.text"
    EMOTE: "MessageType" = "m.emote"
    NOTICE: "MessageType" = "m.notice"
    IMAGE: "MessageType" = "m.image"
    STICKER: "MessageType" = "m.sticker"
    VIDEO: "MessageType" = "m.video"
    AUDIO: "MessageType" = "m.audio"
    FILE: "MessageType" = "m.file"
    LOCATION: "MessageType" = "m.location"

    @property
    def is_text(self) -> bool:
        return self.value in TEXT_MESSAGE_TYPES

    @property
    def is_media(self) -> bool:
        return self.value in MEDIA_MESSAGE_TYPES


# endregion
# region Relations


@dataclass
class InReplyTo(SerializableAttrs):
    event_id: EventID


class RelationType(ExtensibleEnum):
    ANNOTATION: "RelationType" = "m.annotation"
    REFERENCE: "RelationType" = "m.reference"
    REPLACE: "RelationType" = "m.replace"
    THREAD: "RelationType" = "m.thread"


@dataclass
class RelatesTo(SerializableAttrs):
    """Message relations. Used for reactions, edits and replies."""

    rel_type: RelationType = None
    event_id: Optional[EventID] = None
    key: Optional[str] = None
    is_falling_back: Optional[bool] = None
    in_reply_to: Optional[InReplyTo] = field(default=None, json="m.in_reply_to")

    def __bool__(self) -> bool:
        return (bool(self.rel_type) and bool(self.event_id)) or bool(self.in_reply_to)

    def serialize(self) -> JSON:
        if not self:
            return attr.NOTHING
        return super().serialize()


# endregion
# region Base event content


class BaseMessageEventContentFuncs:
    """Base class for the contents of all message-type events (currently m.room.message and
    m.sticker). Contains relation helpers."""

    body: str
    _relates_to: Optional[RelatesTo]

    def set_reply(self, reply_to: Union[EventID, "MessageEvent"], **kwargs) -> None:
        self.relates_to.in_reply_to = InReplyTo(
            event_id=reply_to if isinstance(reply_to, str) else reply_to.event_id
        )

    def set_thread_parent(
        self,
        thread_parent: Union[EventID, "MessageEvent"],
        last_event_in_thread: Union[EventID, "MessageEvent", None] = None,
        disable_reply_fallback: bool = False,
        **kwargs,
    ) -> None:
        self.relates_to.rel_type = RelationType.THREAD
        self.relates_to.event_id = (
            thread_parent if isinstance(thread_parent, str) else thread_parent.event_id
        )
        if not disable_reply_fallback:
            self.set_reply(last_event_in_thread or thread_parent, **kwargs)
            self.relates_to.is_falling_back = True

    def set_edit(self, edits: Union[EventID, "MessageEvent"]) -> None:
        self.relates_to.rel_type = RelationType.REPLACE
        self.relates_to.event_id = edits if isinstance(edits, str) else edits.event_id
        # Library consumers may create message content by setting a reply first,
        # then later marking it as an edit. As edits can't change the reply, just remove
        # the reply metadata when marking as a reply.
        if self.relates_to.in_reply_to:
            self.relates_to.in_reply_to = None
            self.relates_to.is_falling_back = None

    def serialize(self) -> JSON:
        data = SerializableAttrs.serialize(self)
        evt = self.get_edit()
        if evt:
            new_content = {**data}
            del new_content["m.relates_to"]
            data["m.new_content"] = new_content
            if "body" in data:
                data["body"] = f"* {data['body']}"
            if "formatted_body" in data:
                data["formatted_body"] = f"* {data['formatted_body']}"
        return data

    @property
    def relates_to(self) -> RelatesTo:
        if self._relates_to is None:
            self._relates_to = RelatesTo()
        return self._relates_to

    @relates_to.setter
    def relates_to(self, relates_to: RelatesTo) -> None:
        self._relates_to = relates_to

    def get_reply_to(self) -> Optional[EventID]:
        if self._relates_to and self._relates_to.in_reply_to:
            return self._relates_to.in_reply_to.event_id
        return None

    def get_edit(self) -> Optional[EventID]:
        if self._relates_to and self._relates_to.rel_type == RelationType.REPLACE:
            return self._relates_to.event_id
        return None

    def get_thread_parent(self) -> Optional[EventID]:
        if self._relates_to and self._relates_to.rel_type == RelationType.THREAD:
            return self._relates_to.event_id
        return None

    def trim_reply_fallback(self) -> None:
        pass


@dataclass
class BaseMessageEventContent(BaseMessageEventContentFuncs):
    """Base event content for all m.room.message-type events."""

    msgtype: MessageType = None
    body: str = ""

    external_url: str = None
    _relates_to: Optional[RelatesTo] = attr.ib(default=None, metadata={"json": "m.relates_to"})


# endregion
# region Media info


@dataclass
class JSONWebKey(SerializableAttrs):
    key: str = attr.ib(metadata={"json": "k"})
    algorithm: str = attr.ib(default="A256CTR", metadata={"json": "alg"})
    extractable: bool = attr.ib(default=True, metadata={"json": "ext"})
    key_type: str = attr.ib(default="oct", metadata={"json": "kty"})
    key_ops: List[str] = attr.ib(factory=lambda: ["encrypt", "decrypt"])


@dataclass
class EncryptedFile(SerializableAttrs):
    key: JSONWebKey
    iv: str
    hashes: Dict[str, str]
    url: Optional[ContentURI] = None
    version: str = attr.ib(default="v2", metadata={"json": "v"})


@dataclass
class BaseFileInfo(SerializableAttrs):
    mimetype: str = None
    size: int = None


@dataclass
class ThumbnailInfo(BaseFileInfo, SerializableAttrs):
    """Information about the thumbnail for a document, video, image or location."""

    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    orientation: int = None


@dataclass
class FileInfo(BaseFileInfo, SerializableAttrs):
    """Information about a document message."""

    thumbnail_info: Optional[ThumbnailInfo] = None
    thumbnail_file: Optional[EncryptedFile] = None
    thumbnail_url: Optional[ContentURI] = None


@dataclass
class ImageInfo(FileInfo, SerializableAttrs):
    """Information about an image message."""

    height: int = attr.ib(default=None, metadata={"json": "h"})
    width: int = attr.ib(default=None, metadata={"json": "w"})
    orientation: int = None


@dataclass
class VideoInfo(ImageInfo, SerializableAttrs):
    """Information about a video message."""

    duration: int = None
    orientation: int = None


@dataclass
class AudioInfo(BaseFileInfo, SerializableAttrs):
    """Information about an audio message."""

    duration: int = None


MediaInfo = Union[ImageInfo, VideoInfo, AudioInfo, FileInfo, Obj]


@dataclass
class LocationInfo(SerializableAttrs):
    """Information about a location message."""

    thumbnail_url: Optional[ContentURI] = None
    thumbnail_info: Optional[ThumbnailInfo] = None
    thumbnail_file: Optional[EncryptedFile] = None


# endregion
# region Event content


@dataclass
class MediaMessageEventContent(BaseMessageEventContent, SerializableAttrs):
    """The content of a media message event (m.image, m.audio, m.video, m.file)"""

    url: Optional[ContentURI] = None
    info: Optional[MediaInfo] = None
    file: Optional[EncryptedFile] = None

    @staticmethod
    @deserializer(MediaInfo)
    @deserializer(Optional[MediaInfo])
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
class LocationMessageEventContent(BaseMessageEventContent, SerializableAttrs):
    geo_uri: str = None
    info: LocationInfo = None


html_reply_fallback_regex: Pattern = re.compile(r"^<mx-reply>[\s\S]+</mx-reply>")


@dataclass
class TextMessageEventContent(BaseMessageEventContent, SerializableAttrs):
    """The content of a text message event (m.text, m.notice, m.emote)"""

    format: Format = None
    formatted_body: str = None

    def set_reply(
        self, reply_to: Union["MessageEvent", EventID], *, displayname: Optional[str] = None
    ) -> None:
        super().set_reply(reply_to)
        if isinstance(reply_to, str):
            return
        if isinstance(reply_to, MessageEvent):
            self.ensure_has_html()
            if isinstance(reply_to.content, TextMessageEventContent):
                reply_to.content.trim_reply_fallback()
            self.formatted_body = (
                reply_to.make_reply_fallback_html(displayname) + self.formatted_body
            )
            self.body = reply_to.make_reply_fallback_text(displayname) + self.body

    def ensure_has_html(self) -> None:
        if not self.formatted_body or self.format != Format.HTML:
            self.format = Format.HTML
            self.formatted_body = escape(self.body).replace("\n", "<br/>")

    def formatted(self, format: Format) -> Optional[str]:
        if self.format == format:
            return self.formatted_body
        return None

    def trim_reply_fallback(self) -> None:
        if self.get_reply_to() and not getattr(self, "__reply_fallback_trimmed", False):
            self._trim_reply_fallback_text()
            self._trim_reply_fallback_html()
            setattr(self, "__reply_fallback_trimmed", True)

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


MessageEventContent = Union[
    TextMessageEventContent, MediaMessageEventContent, LocationMessageEventContent, Obj
]


# endregion


@dataclass
class MessageUnsigned(BaseUnsigned, SerializableAttrs):
    """Unsigned information sent with message events."""

    transaction_id: str = None


html_reply_fallback_format = (
    "<mx-reply><blockquote>"
    "<a href='https://matrix.to/#/{room_id}/{event_id}'>In reply to</a> "
    "<a href='https://matrix.to/#/{sender}'>{displayname}</a><br/>"
    "{content}"
    "</blockquote></mx-reply>"
)

media_reply_fallback_body_map = {
    MessageType.IMAGE: "an image",
    MessageType.STICKER: "a sticker",
    MessageType.AUDIO: "audio",
    MessageType.VIDEO: "a video",
    MessageType.FILE: "a file",
    MessageType.LOCATION: "a location",
}


@dataclass
class MessageEvent(BaseRoomEvent, SerializableAttrs):
    """An m.room.message event"""

    content: MessageEventContent
    unsigned: Optional[MessageUnsigned] = field(factory=lambda: MessageUnsigned())

    @staticmethod
    @deserializer(MessageEventContent)
    def deserialize_content(data: JSON) -> MessageEventContent:
        if not isinstance(data, dict):
            return Obj()
        rel = data.get("m.relates_to", None) or {}
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

    def make_reply_fallback_html(self, displayname: Optional[str] = None) -> str:
        """Generate the HTML fallback for messages replying to this event."""
        if self.content.msgtype.is_text:
            body = self.content.formatted_body or escape(self.content.body).replace("\n", "<br/>")
        else:
            sent_type = media_reply_fallback_body_map[self.content.msgtype] or "a message"
            body = f"sent {sent_type}"
        displayname = escape(displayname) if displayname else self.sender
        return html_reply_fallback_format.format(
            room_id=self.room_id,
            event_id=self.event_id,
            sender=self.sender,
            displayname=displayname,
            content=body,
        )

    def make_reply_fallback_text(self, displayname: Optional[str] = None) -> str:
        """Generate the plaintext fallback for messages replying to this event."""
        if self.content.msgtype.is_text:
            body = self.content.body
        else:
            try:
                body = media_reply_fallback_body_map[self.content.msgtype]
            except KeyError:
                body = "an unknown message type"
        lines = body.strip().split("\n")
        first_line, lines = lines[0], lines[1:]
        fallback_text = f"> <{displayname or self.sender}> {first_line}"
        for line in lines:
            fallback_text += f"\n> {line}"
        fallback_text += "\n\n"
        return fallback_text
