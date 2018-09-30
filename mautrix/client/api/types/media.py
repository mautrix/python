import attr

from .util import SerializableAttrs


@attr.s(auto_attribs=True)
class MediaRepoConfig(SerializableAttrs['MediaRepoConfig']):
    upload_size: int = attr.ib(metadata={"json": "m.upload_size"})
