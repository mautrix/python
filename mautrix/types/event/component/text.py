# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import FrozenSet, Generator, List, Optional, Union

from attr import dataclass

from ...primitive import JSON
from ...util import Serializable, SerializableAttrs, field
from . import key

TEXT_MIME = "text/plain"
HTML_MIME = "text/html"


@dataclass
class MessagePart(SerializableAttrs):
    body: str
    mimetype: str


class Message(List[MessagePart], Serializable):
    def __getitem__(self, item: Union[int, str]) -> MessagePart:
        if isinstance(item, str):
            try:
                return next(self.get_all_by_mime(item))
            except StopIteration as e:
                raise KeyError(item) from e
        else:
            return super().__getitem__(item)

    def get_all_by_mime(self, mimetype: str) -> Generator[MessagePart, None, None]:
        return (item for item in self if item.mimetype == mimetype)

    def get_one_by_mime(
        self, mimetype: str, default: Optional[MessagePart] = None
    ) -> Optional[MessagePart]:
        try:
            return self[mimetype]
        except KeyError:
            return default

    @property
    def text(self) -> Optional[str]:
        try:
            return self[TEXT_MIME].body
        except KeyError:
            return None

    @property
    def html(self) -> Optional[str]:
        try:
            return self[HTML_MIME].body
        except KeyError:
            return None

    @property
    def mimetypes(self) -> FrozenSet[str]:
        return frozenset(item.mimetype for item in self)

    def serialize(self) -> JSON:
        mimes = self.mimetypes
        if mimes == {TEXT_MIME}:
            return {key.TEXT: self.text}
        elif mimes == {TEXT_MIME, HTML_MIME}:
            return {key.TEXT: self.text, key.HTML: self.html}
        else:
            return {key.MESSAGE: self}

    @classmethod
    def deserialize_shorthand(cls, raw: JSON) -> Optional["Message"]:
        try:
            text = raw[key.TEXT]
        except KeyError:
            return None

        output = cls()
        output.append(MessagePart(mimetype=TEXT_MIME, body=text))
        try:
            html = raw[key.HTML]
        except KeyError:
            pass
        else:
            output.append(MessagePart(mimetype=HTML_MIME, body=html))
        return output

    @classmethod
    def deserialize(cls, raw: JSON) -> "Message":
        output = cls.deserialize_shorthand(raw)
        if output:
            return output
        return cls(MessagePart.deserialize(part) for part in raw[key.MESSAGE])
