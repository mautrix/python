# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from attr import dataclass
import attr

from .primitive import ContentURI
from .util import SerializableAttrs


@dataclass
class MediaRepoConfig(SerializableAttrs):
    """
    Matrix media repo config. See `GET /_matrix/media/r0/config`_.

    .. _GET /_matrix/media/r0/config:
        https://matrix.org/docs/spec/client_server/r0.5.0#get-matrix-media-r0-config
    """

    upload_size: int = attr.ib(metadata={"json": "m.upload.size"})


@dataclass
class OpenGraphImage(SerializableAttrs):
    url: ContentURI = attr.ib(default=None, metadata={"json": "og:image"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:image:type"})
    height: int = attr.ib(default=None, metadata={"json": "og:image:width"})
    width: int = attr.ib(default=None, metadata={"json": "og:image:height"})
    size: int = attr.ib(default=None, metadata={"json": "matrix:image:size"})


@dataclass
class OpenGraphVideo(SerializableAttrs):
    url: ContentURI = attr.ib(default=None, metadata={"json": "og:video"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:video:type"})
    height: int = attr.ib(default=None, metadata={"json": "og:video:width"})
    width: int = attr.ib(default=None, metadata={"json": "og:video:height"})
    size: int = attr.ib(default=None, metadata={"json": "matrix:video:size"})


@dataclass
class OpenGraphAudio(SerializableAttrs):
    url: ContentURI = attr.ib(default=None, metadata={"json": "og:audio"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:audio:type"})


@dataclass
class MXOpenGraph(SerializableAttrs):
    """
    Matrix URL preview response. See `GET /_matrix/media/r0/preview_url`_.

    .. _GET /_matrix/media/r0/preview_url:
        https://matrix.org/docs/spec/client_server/r0.5.0#get-matrix-media-r0-preview-url
    """

    title: str = attr.ib(default=None, metadata={"json": "og:title"})
    description: str = attr.ib(default=None, metadata={"json": "og:description"})
    image: OpenGraphImage = attr.ib(default=None, metadata={"flatten": True})
    video: OpenGraphVideo = attr.ib(default=None, metadata={"flatten": True})
    audio: OpenGraphAudio = attr.ib(default=None, metadata={"flatten": True})
