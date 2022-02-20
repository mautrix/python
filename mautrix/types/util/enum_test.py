# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from attr import dataclass

from .enum import ExtensibleEnum
from .serializable_attrs import SerializableAttrs


def test_extensible_enum_int():
    class Hello(ExtensibleEnum):
        HI = 1
        HMM = 2

    assert Hello.HI.value == 1
    assert Hello.HI.key == "HI"
    assert 1 in Hello
    assert Hello(1) == Hello.HI
    assert Hello["HMM"] == Hello.HMM

    assert len(Hello) == 2
    hello3 = Hello(3)
    assert hello3.value == 3
    assert not hello3.key
    Hello.YAY = hello3
    assert len(Hello) == 3
    assert hello3.key == "YAY"

    @dataclass
    class Wrapper(SerializableAttrs):
        hello: Hello

    assert Wrapper.deserialize({"hello": 1}).hello == Hello.HI
    assert Wrapper.deserialize({"hello": 2}).hello == Hello.HMM
    assert Wrapper.deserialize({"hello": 3}).hello == hello3
    assert Wrapper.deserialize({"hello": 4}).hello.value == 4


def test_extensible_enum_str():
    class Hello(ExtensibleEnum):
        HI = "hi"
        HMM = "🤔"

    assert Hello.HI.value == "hi"
    assert Hello.HI.key == "HI"
    assert "🤔" in Hello
    assert Hello("🤔") == Hello.HMM
    assert Hello["HI"] == Hello.HI

    assert len(Hello) == 2
    hello3 = Hello("yay")
    assert hello3.value == "yay"
    assert not hello3.key
    Hello.YAY = hello3
    assert len(Hello) == 3
    assert hello3.key == "YAY"

    @dataclass
    class Wrapper(SerializableAttrs):
        hello: Hello

    assert Wrapper.deserialize({"hello": "hi"}).hello == Hello.HI
    assert Wrapper.deserialize({"hello": "🤔"}).hello == Hello.HMM
    assert Wrapper.deserialize({"hello": "yay"}).hello == hello3
    assert Wrapper.deserialize({"hello": "thonk"}).hello.value == "thonk"
