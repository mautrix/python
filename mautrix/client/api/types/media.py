from attr import dataclass
import attr

from .primitive import ContentURI
from .util import SerializableAttrs


@dataclass
class MediaRepoConfig(SerializableAttrs['MediaRepoConfig']):
    upload_size: int = attr.ib(metadata={"json": "m.upload_size"})


@dataclass
class OpenGraphImage(SerializableAttrs['OpenGraphImage']):
    url: ContentURI = attr.ib(default=None, metadata={"json": "og:image"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:image:type"})
    height: int = attr.ib(default=None, metadata={"json": "og:image:width"})
    width: int = attr.ib(default=None, metadata={"json": "og:image:height"})
    size: int = attr.ib(default=None, metadata={"json": "matrix:image:size"})


@dataclass
class OpenGraphVideo(SerializableAttrs['OpenGraphVideo']):
    url: ContentURI = attr.ib(default=None, metadata={"json": "og:video"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:video:type"})
    height: int = attr.ib(default=None, metadata={"json": "og:video:width"})
    width: int = attr.ib(default=None, metadata={"json": "og:video:height"})
    size: int = attr.ib(default=None, metadata={"json": "matrix:video:size"})


@dataclass
class OpenGraphAudio(SerializableAttrs['OpenGraphAudio']):
    url: ContentURI = attr.ib(default=None, metadata={"json": "og:audio"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:audio:type"})


@dataclass
class MXOpenGraph(SerializableAttrs['MXOpenGraph']):
    title: str = attr.ib(default=None, metadata={"json": "og:title"})
    description: str = attr.ib(default=None, metadata={"json": "og:description"})
    image: OpenGraphImage = attr.ib(default=None, metadata={"flatten": True})
    video: OpenGraphVideo = attr.ib(default=None, metadata={"flatten": True})
    audio: OpenGraphAudio = attr.ib(default=None, metadata={"flatten": True})
