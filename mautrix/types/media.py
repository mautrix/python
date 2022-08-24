# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional

from attr import dataclass

from .primitive import ContentURI
from .util import SerializableAttrs, field


@dataclass
class MediaRepoConfig(SerializableAttrs):
    """
    Matrix media repo config. See `GET /_matrix/media/v3/config`_.

    .. _GET /_matrix/media/v3/config:
        https://spec.matrix.org/v1.2/client-server-api/#get_matrixmediav3config
    """

    upload_size: int = field(json="m.upload.size")


@dataclass
class OpenGraphImage(SerializableAttrs):
    url: ContentURI = field(default=None, json="og:image")
    mimetype: str = field(default=None, json="og:image:type")
    height: int = field(default=None, json="og:image:width")
    width: int = field(default=None, json="og:image:height")
    size: int = field(default=None, json="matrix:image:size")


@dataclass
class OpenGraphVideo(SerializableAttrs):
    url: ContentURI = field(default=None, json="og:video")
    mimetype: str = field(default=None, json="og:video:type")
    height: int = field(default=None, json="og:video:width")
    width: int = field(default=None, json="og:video:height")
    size: int = field(default=None, json="matrix:video:size")


@dataclass
class OpenGraphAudio(SerializableAttrs):
    url: ContentURI = field(default=None, json="og:audio")
    mimetype: str = field(default=None, json="og:audio:type")


@dataclass
class MXOpenGraph(SerializableAttrs):
    """
    Matrix URL preview response. See `GET /_matrix/media/v3/preview_url`_.

    .. _GET /_matrix/media/v3/preview_url:
        https://spec.matrix.org/v1.2/client-server-api/#get_matrixmediav3preview_url
    """

    title: str = field(default=None, json="og:title")
    description: str = field(default=None, json="og:description")
    image: OpenGraphImage = field(default=None, flatten=True)
    video: OpenGraphVideo = field(default=None, flatten=True)
    audio: OpenGraphAudio = field(default=None, flatten=True)


@dataclass
class MediaCreateResponse(SerializableAttrs):
    """
    Matrix media create response including MSC3870
    """

    content_uri: ContentURI
    unused_expired_at: Optional[int] = None
    upload_url: Optional[str] = None
