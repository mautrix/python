# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Optional

from attr import dataclass
import pytest

from .serializable_attrs import SerializableAttrs, SerializerError, field


def test_simple_class():
    @dataclass
    class Foo(SerializableAttrs):
        hello: int
        world: str

    serialized = {"hello": 5, "world": "hi"}
    deserialized = Foo.deserialize(serialized)
    assert deserialized == Foo(5, "hi")
    assert deserialized.serialize() == serialized

    with pytest.raises(SerializerError):
        Foo.deserialize({"world": "hi"})


def test_default():
    @dataclass
    class Default(SerializableAttrs):
        no_default: int
        defaultful_value: int = 5

    d1 = Default.deserialize({"no_default": 3})
    assert d1.no_default == 3
    assert d1.defaultful_value == 5
    d2 = Default.deserialize({"no_default": 4, "defaultful_value": 6})
    assert d2.no_default == 4
    assert d2.defaultful_value == 6


def test_factory():
    @dataclass
    class Factory(SerializableAttrs):
        manufactured_value: List[str] = field(factory=lambda: ["hi"])

    assert Factory.deserialize({}).manufactured_value == ["hi"]
    assert Factory.deserialize({"manufactured_value": None}).manufactured_value == ["hi"]
    factory1 = Factory.deserialize({})
    factory2 = Factory.deserialize({})
    assert factory1.manufactured_value is not factory2.manufactured_value
    assert Factory.deserialize({"manufactured_value": ["bye"]}).manufactured_value == ["bye"]


def test_hidden():
    @dataclass
    class HiddenField(SerializableAttrs):
        visible: str
        hidden: int = field(hidden=True, default=5)

    deserialized_hidden = HiddenField.deserialize({"visible": "yay", "hidden": 4})
    assert deserialized_hidden.hidden == 5
    assert deserialized_hidden.unrecognized_["hidden"] == 4
    assert HiddenField("hmm", 5).serialize() == {"visible": "hmm"}


def test_ignore_errors():
    @dataclass
    class Something(SerializableAttrs):
        required: bool

    @dataclass
    class Wrapper(SerializableAttrs):
        something: Optional[Something] = field(ignore_errors=True)

    @dataclass
    class ErroringWrapper(SerializableAttrs):
        something: Optional[Something] = field(ignore_errors=False)

    assert Wrapper.deserialize({"something": {"required": True}}) == Wrapper(Something(True))
    assert Wrapper.deserialize({"something": {}}) == Wrapper(None)
    with pytest.raises(SerializerError):
        ErroringWrapper.deserialize({"something": 5})
    with pytest.raises(SerializerError):
        ErroringWrapper.deserialize({"something": {}})


def test_json_key_override():
    @dataclass
    class Meow(SerializableAttrs):
        meow: int = field(json="fi.mau.namespaced_meow")

    serialized = {"fi.mau.namespaced_meow": 123}
    deserialized = Meow.deserialize(serialized)
    assert deserialized == Meow(123)
    assert deserialized.serialize() == serialized


def test_omit_empty():
    @dataclass
    class OmitEmpty(SerializableAttrs):
        omitted: Optional[int] = field(omit_empty=True)

    @dataclass
    class DontOmitEmpty(SerializableAttrs):
        not_omitted: Optional[int] = field(omit_empty=False)

    assert OmitEmpty(None).serialize() == {}
    assert OmitEmpty(0).serialize() == {"omitted": 0}
    assert DontOmitEmpty(None).serialize() == {"not_omitted": None}
    assert DontOmitEmpty(0).serialize() == {"not_omitted": 0}


def test_omit_default():
    @dataclass
    class OmitDefault(SerializableAttrs):
        omitted: int = field(default=5, omit_default=True)

    @dataclass
    class DontOmitDefault(SerializableAttrs):
        not_omitted: int = 5

    assert OmitDefault().serialize() == {}
    assert OmitDefault(5).serialize() == {}
    assert OmitDefault(6).serialize() == {"omitted": 6}
    assert DontOmitDefault().serialize() == {"not_omitted": 5}
    assert DontOmitDefault(5).serialize() == {"not_omitted": 5}
    assert DontOmitDefault(6).serialize() == {"not_omitted": 6}


def test_flatten():
    from mautrix.types import ContentURI

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
        title: str = field(default=None, json="og:title")
        description: str = field(default=None, json="og:description")
        image: OpenGraphImage = field(default=None, flatten=True)
        video: OpenGraphVideo = field(default=None, flatten=True)
        audio: OpenGraphAudio = field(default=None, flatten=True)

    example_com_preview = {
        "og:title": "Example Domain",
        "og:description": "Example Domain\n\nThis domain is for use in illustrative examples in "
        "documents. You may use this domain in literature without prior "
        "coordination or asking for permission.\n\nMore information...",
    }
    google_com_preview = {
        "og:title": "Google",
        "og:image": "mxc://maunium.net/2021-06-20_jkscuJXkHjvzNaUJ",
        "og:description": "Search\n\nImages\n\nMaps\n\nPlay\n\nYouTube\n\nNews\n\nGmail\n\n"
        "Drive\n\nMore\n\n\u00bb\n\nWeb History\n\n|\n\nSettings\n\n|\n\n"
        "Sign in\n\nAdvanced search\n\nGoogle offered in:\n\nDeutsch\n\n"
        "AdvertisingPrograms\n\nBusiness Solutions",
        "og:image:width": 128,
        "og:image:height": 128,
        "og:image:type": "image/png",
        "matrix:image:size": 3428,
    }

    example_com_deserialized = MXOpenGraph.deserialize(example_com_preview)
    assert example_com_deserialized.title == "Example Domain"
    assert example_com_deserialized.image is None
    assert example_com_deserialized.video is None
    assert example_com_deserialized.audio is None
    google_com_deserialized = MXOpenGraph.deserialize(google_com_preview)
    assert google_com_deserialized.title == "Google"
    assert google_com_deserialized.image is not None
    assert google_com_deserialized.image.url == "mxc://maunium.net/2021-06-20_jkscuJXkHjvzNaUJ"
    assert google_com_deserialized.image.width == 128
    assert google_com_deserialized.image.height == 128
    assert google_com_deserialized.image.mimetype == "image/png"
    assert google_com_deserialized.image.size == 3428
    assert google_com_deserialized.video is None
    assert google_com_deserialized.audio is None
