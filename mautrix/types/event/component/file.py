# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Optional, cast

from attr import dataclass

from ...primitive import JSON, ContentURI
from ...util import SerializableAttrs, field
from .text import Message


@dataclass
class JSONWebKey(SerializableAttrs):
    key: str = field(json="k")
    algorithm: str = field(json="alg", default="A256CTR")
    extractable: bool = field(json="ext", default=True)
    key_type: str = field(json="kty", default="oct")
    key_ops: List[str] = field(factory=lambda: ["encrypt", "decrypt"])


@dataclass
class EncryptedFile(SerializableAttrs):
    key: JSONWebKey
    iv: str
    hashes: Dict[str, str]
    version: str = field(json="v", default="v2")

    @classmethod
    def deserialize(cls, data: JSON) -> Optional["EncryptedFile"]:
        if "key" in data:
            return cast(cls, super().deserialize(data))
        return None


@dataclass
class File(SerializableAttrs):
    url: ContentURI
    name: Optional[str] = None
    mimetype: Optional[str] = None
    size: Optional[int] = None
    encrypted: Optional[EncryptedFile] = field(default=None, flatten=True)


@dataclass
class Image(SerializableAttrs):
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class ThumbnailItem(
    Image,
    File,
    SerializableAttrs,
):
    pass


@dataclass
class Audio(SerializableAttrs):
    duration: Optional[int] = None
    waveform: Optional[List[int]] = None


@dataclass
class Video(Image, SerializableAttrs):
    duration: Optional[int] = None
