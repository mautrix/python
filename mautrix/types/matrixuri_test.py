# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import NamedTuple

import pytest

from .matrixuri import IdentifierType, MatrixURI, MatrixURIError, URIAction, _PathPart
from .primitive import EventID, RoomAlias, RoomID, UserID


def test_basic_parse_uri() -> None:
    for test in basic_tests:
        assert MatrixURI.parse(test.uri) == test.parsed


def test_basic_stringify_uri() -> None:
    for test in basic_tests:
        assert test.uri == test.parsed.matrix_uri


def test_basic_parse_url() -> None:
    for test in basic_tests:
        assert MatrixURI.parse(test.url) == test.parsed


def test_basic_stringify_url() -> None:
    for test in basic_tests:
        assert test.url == test.parsed.matrix_to_url


def test_basic_build() -> None:
    for test in basic_tests:
        assert MatrixURI.build(*test.params) == test.parsed


def test_parse_unescaped() -> None:
    assert MatrixURI.parse("https://matrix.to/#/#hello:world").room_alias == "#hello:world"


def test_parse_trailing_slash() -> None:
    assert MatrixURI.parse("https://matrix.to/#/#hello:world/").room_alias == "#hello:world"
    assert MatrixURI.parse("matrix:r/hello:world/").room_alias == "#hello:world"


def test_parse_errors() -> None:
    tests = [
        "https://example.com",
        "matrix:invalid/foo",
        "matrix:hello world",
        "matrix:/roomid",
        "matrix:roomid/",
        "matrix:roomid/foo/e/",
        "matrix:roomid/foo/e",
        "https://matrix.to",
        "https://matrix.to/#/",
        "https://matrix.to/#foo/#hello:world",
        "https://matrix.to/#/#hello:world/hmm",
    ]
    for test in tests:
        with pytest.raises(MatrixURIError):
            print(MatrixURI.parse(test))


def test_build_errors() -> None:
    with pytest.raises(ValueError):
        MatrixURI.build("hello world")
    with pytest.raises(ValueError):
        MatrixURI.build(EventID("$uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s"))
    with pytest.raises(ValueError):
        MatrixURI.build(
            UserID("@user:example.org"),
            EventID("$uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s"),
        )
    with pytest.raises(ValueError):
        MatrixURI.build(
            RoomID("!room:example.org"),
            RoomID("!anotherroom:example.com"),
        )
    with pytest.raises(ValueError):
        MatrixURI.build(
            RoomID("!room:example.org"),
            "hmm",
        )


def _make_parsed(
    part1: _PathPart,
    part2: _PathPart | None = None,
    via: list[str] | None = None,
    action: URIAction | None = None,
) -> MatrixURI:
    uri = MatrixURI()
    uri._part1 = part1
    uri._part2 = part2
    uri.via = via
    uri.action = action
    return uri


class BasicTestItems(NamedTuple):
    url: str
    uri: str
    parsed: MatrixURI
    params: tuple[RoomID | UserID | RoomAlias, EventID | None, list[str] | None, URIAction | None]


basic_tests = [
    BasicTestItems(
        "https://matrix.to/#/%217NdBVvkd4aLSbgKt9RXl%3Aexample.org",
        "matrix:roomid/7NdBVvkd4aLSbgKt9RXl:example.org",
        _make_parsed(_PathPart(IdentifierType.ROOM_ID, "7NdBVvkd4aLSbgKt9RXl:example.org")),
        (RoomID("!7NdBVvkd4aLSbgKt9RXl:example.org"), None, None, None),
    ),
    BasicTestItems(
        "https://matrix.to/#/%217NdBVvkd4aLSbgKt9RXl%3Aexample.org?via=maunium.net&via=matrix.org",
        "matrix:roomid/7NdBVvkd4aLSbgKt9RXl:example.org?via=maunium.net&via=matrix.org",
        _make_parsed(
            _PathPart(IdentifierType.ROOM_ID, "7NdBVvkd4aLSbgKt9RXl:example.org"),
            via=["maunium.net", "matrix.org"],
        ),
        (RoomID("!7NdBVvkd4aLSbgKt9RXl:example.org"), None, ["maunium.net", "matrix.org"], None),
    ),
    BasicTestItems(
        "https://matrix.to/#/%23someroom%3Aexample.org",
        "matrix:r/someroom:example.org",
        _make_parsed(_PathPart(IdentifierType.ROOM_ALIAS, "someroom:example.org")),
        (RoomAlias("#someroom:example.org"), None, None, None),
    ),
    BasicTestItems(
        "https://matrix.to/#/%217NdBVvkd4aLSbgKt9RXl%3Aexample.org/%24uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s",
        "matrix:roomid/7NdBVvkd4aLSbgKt9RXl:example.org/e/uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s",
        _make_parsed(
            _PathPart(IdentifierType.ROOM_ID, "7NdBVvkd4aLSbgKt9RXl:example.org"),
            _PathPart(IdentifierType.EVENT, "uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s"),
        ),
        (
            RoomID("!7NdBVvkd4aLSbgKt9RXl:example.org"),
            EventID("$uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s"),
            None,
            None,
        ),
    ),
    BasicTestItems(
        "https://matrix.to/#/%23someroom%3Aexample.org/%24uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s",
        "matrix:r/someroom:example.org/e/uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s",
        _make_parsed(
            _PathPart(IdentifierType.ROOM_ALIAS, "someroom:example.org"),
            _PathPart(IdentifierType.EVENT, "uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s"),
        ),
        (
            RoomAlias("#someroom:example.org"),
            EventID("$uOH4C9cK4HhMeFWkUXMbdF_dtndJ0j9je-kIK3XpV1s"),
            None,
            None,
        ),
    ),
    BasicTestItems(
        "https://matrix.to/#/%40user%3Aexample.org",
        "matrix:u/user:example.org",
        _make_parsed(_PathPart(IdentifierType.USER, "user:example.org")),
        (UserID("@user:example.org"), None, None, None),
    ),
]
