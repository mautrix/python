import attr

from .util import SerializableAttrs


@attr.s(auto_attribs=True)
class MediaRepoConfig(SerializableAttrs['MediaRepoConfig']):
    upload_size: int = attr.ib(metadata={"json": "m.upload_size"})


@attr.s(auto_attribs=True)
class OpenGraphImage(SerializableAttrs['OpenGraphImage']):
    url: str = attr.ib(default=None, metadata={"json": "og:image"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:image:type"})
    height: int = attr.ib(default=None, metadata={"json": "og:image:width"})
    width: int = attr.ib(default=None, metadata={"json": "og:image:height"})
    size: int = attr.ib(default=None, metadata={"json": "matrix:image:size"})


@attr.s(auto_attribs=True)
class OpenGraphVideo(SerializableAttrs['OpenGraphVideo']):
    url: str = attr.ib(default=None, metadata={"json": "og:video"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:video:type"})
    height: int = attr.ib(default=None, metadata={"json": "og:video:width"})
    width: int = attr.ib(default=None, metadata={"json": "og:video:height"})
    size: int = attr.ib(default=None, metadata={"json": "matrix:video:size"})


@attr.s(auto_attribs=True)
class OpenGraphAudio(SerializableAttrs['OpenGraphAudio']):
    url: str = attr.ib(default=None, metadata={"json": "og:audio"})
    mimetype: str = attr.ib(default=None, metadata={"json": "og:audio:type"})


@attr.s(auto_attribs=True)
class MXOpenGraph(SerializableAttrs['MXOpenGraph']):
    title: str = attr.ib(default=None, metadata={"json": "og:title"})
    description: str = attr.ib(default=None, metadata={"json": "og:description"})
    image: OpenGraphImage = attr.ib(default=None, metadata={"flatten": True})
    video: OpenGraphVideo = attr.ib(default=None, metadata={"flatten": True})
    audio: OpenGraphAudio = attr.ib(default=None, metadata={"flatten": True})
