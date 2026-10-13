# Copyright (c) 2026 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import inspect

import pytest

from .obj import Obj


def test_obj_basic_attribute_access():
    o = Obj(name="hello", count=3)
    assert o.name == "hello"
    assert o.count == 3


def test_obj_trailing_underscore_keyword_escape():
    # The single trailing underscore is the documented escape hatch for
    # Python keywords (e.g. ``obj.from_``); rstrip("_") still maps it to
    # the same backing key.
    o = Obj(**{"from": "@user"})
    assert o.from_ == "@user"


def test_obj_dunder_attribute_raises():
    # Regression for issue #176: probing tools like ``inspect.unwrap``
    # would auto-vivify ``__wrapped__`` and put the object into a state
    # where repr/serialize recurses until RecursionError.
    o = Obj()
    with pytest.raises(AttributeError):
        o.__wrapped__
    with pytest.raises(AttributeError):
        o.__custom_thing__
    # The attribute must NOT have been stored.
    assert "__wrapped__" not in o.__dict__
    assert "__wrapped" not in o.__dict__


def test_obj_sunder_attribute_raises():
    # IPython's ``_ipython_canary_method_should_not_exist_`` (a sunder
    # name) used to leak into the object's dict via __getattr__.
    o = Obj()
    with pytest.raises(AttributeError):
        o._ipython_canary_method_should_not_exist_
    assert "_ipython_canary_method_should_not_exist" not in o.__dict__


def test_obj_inspect_unwrap_does_not_recurse():
    # End-to-end version of the original report.
    o = Obj()
    # inspect.unwrap probes ``__wrapped__``; with the dunder guard in
    # place it gets an AttributeError on the first try and returns the
    # original object instead of looping until RecursionError.
    assert inspect.unwrap(o) is o
    # And the object must still be safely serializable / printable
    # afterwards.
    assert o.serialize() == {}
    assert repr(o) == "{}"
