# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import ClassVar, NamedTuple
from enum import Enum
import urllib.parse

from yarl import URL

from .primitive import EventID, RoomAlias, RoomID, UserID
from .util import ExtensibleEnum


class IdentifierType(Enum):
    """The type qualifier for entities in a Matrix URI."""

    EVENT = "$"
    USER = "@"
    ROOM_ALIAS = "#"
    ROOM_ID = "!"

    @property
    def sigil(self) -> str:
        """The sigil of the identifier, used in Matrix events, matrix.to URLs and other places"""
        return _type_to_sigil[self]

    @property
    def uri_type_qualifier(self) -> str:
        """The type qualifier of the identifier, only used in ``matrix:`` URIs."""
        return _type_to_path[self]

    @classmethod
    def from_sigil(cls, sigil: str) -> IdentifierType:
        """Get the IdentifierType corresponding to the given sigil."""
        return _sigil_to_type[sigil]

    @classmethod
    def from_uri_type_qualifier(cls, uri_type_qualifier: str) -> IdentifierType:
        """Get the IdentifierType corresponding to the given ``matrix:`` URI type qualifier."""
        return _path_to_type[uri_type_qualifier]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class URIAction(ExtensibleEnum):
    """Represents an intent for what the client should do with a Matrix URI."""

    JOIN = "join"
    CHAT = "chat"


_type_to_path: dict[IdentifierType, str] = {
    IdentifierType.EVENT: "e",
    IdentifierType.USER: "u",
    IdentifierType.ROOM_ALIAS: "r",
    IdentifierType.ROOM_ID: "roomid",
}
_path_to_type: dict[str, IdentifierType] = {v: k for k, v in _type_to_path.items()}
_type_to_sigil: dict[IdentifierType, str] = {it: it.value for it in IdentifierType}
_sigil_to_type: dict[str, IdentifierType] = {v: k for k, v in _type_to_sigil.items()}


class _PathPart(NamedTuple):
    type: IdentifierType
    identifier: str

    @classmethod
    def from_mxid(cls, mxid: UserID | RoomID | EventID | RoomAlias | str) -> _PathPart:
        return _PathPart(type=IdentifierType.from_sigil(mxid[0]), identifier=mxid[1:])

    @property
    def mxid(self) -> str:
        return f"{self.type.sigil}{self.identifier}"

    def __str__(self) -> str:
        return self.mxid

    def __repr__(self) -> str:
        return f"_PathPart({self.type!r}, {self.identifier!r})"

    def __eq__(self, other: _PathPart) -> bool:
        if not isinstance(other, _PathPart):
            return False
        return other.type == self.type and other.identifier == self.identifier


_uri_base = URL.build(scheme="matrix")


class MatrixURIError(ValueError):
    """Raised by :meth:`MatrixURI.parse` when parsing a URI fails."""


class MatrixURI:
    """
    A container for Matrix URI data. Supports parsing and generating both ``matrix:`` URIs
    and ``https://matrix.to`` URLs with the same interface.
    """

    URI_BY_DEFAULT: ClassVar[bool] = False
    """Whether :meth:`__str__` should return the matrix: URI instead of matrix.to URL."""

    _part1: _PathPart
    _part2: _PathPart | None

    via: list[str] | None
    """Servers that know about the resource. Important for room ID links."""

    action: URIAction | None
    """The intent for what clients should do with the URI."""

    def __init__(self) -> None:
        """Internal initializer for MatrixURI, external users should use
        either :meth:`build` or :meth:`parse`."""
        self._part2 = None
        self.via = None
        self.action = None

    @classmethod
    def build(
        cls,
        part1: RoomID | UserID | RoomAlias,
        part2: EventID | None = None,
        via: list[str] | None = None,
        action: URIAction | None = None,
    ) -> MatrixURI:
        """
        Construct a MatrixURI instance using an identifier.

        Args:
            part1: The first part of the URI, a user ID, room ID, or room alias.
            part2: The second part of the URI. Only event IDs are allowed,
                   and only allowed when the first part is a room ID or alias.
            via: Servers that know about the resource. Important for room ID links.
            action: The intent for what clients should do with the URI.

        Returns:
            The constructed MatrixURI.

        Raises:
            ValueError: if one of the identifiers doesn't have a valid sigil.

        Examples:
            >>> from mautrix.types import MatrixURI, UserID, RoomAlias, EventID
            >>> MatrixURI.build(UserID("@user:example.com")).matrix_to_url
            'https://matrix.to/#/%40user%3Aexample.com'
            >>> MatrixURI.build(UserID("@user:example.com")).matrix_uri
            'matrix:u/user:example.com'
            >>> # Picks the format based on the URI_BY_DEFAULT field.
            >>> # The default value will be changed to True in a later release.
            >>> str(MatrixURI.build(UserID("@user:example.com")))
            'https://matrix.to/#/%40user%3Aexample.com'
            >>> MatrixURI.build(RoomAlias("#room:example.com"), EventID("$abc123")).matrix_uri
            'matrix:r/room:example.com/e/abc123'
        """
        uri = cls()
        try:
            uri._part1 = _PathPart.from_mxid(part1)
        except KeyError as e:
            raise ValueError(f"Invalid sigil in part 1 '{part1[0]}'") from e
        if uri._part1.type == IdentifierType.EVENT:
            raise ValueError(f"Event ID links must have a room ID or alias too")
        if part2:
            try:
                uri._part2 = _PathPart.from_mxid(part2)
            except KeyError as e:
                raise ValueError(f"Invalid sigil in part 2 '{part2[0]}'") from e
            if uri._part2.type != IdentifierType.EVENT:
                raise ValueError("The second part of Matrix URIs can only be an event ID")
            if uri._part1.type not in (IdentifierType.ROOM_ID, IdentifierType.ROOM_ALIAS):
                raise ValueError("Can't create an event ID link without a room link as the base")
        uri.via = via
        uri.action = action
        return uri

    @classmethod
    def try_parse(cls, url: str | URL) -> MatrixURI | None:
        """
        Try to parse a ``matrix:`` URI or ``https://matrix.to`` URL into parts.
        If parsing fails, return ``None`` instead of throwing an error.

        Args:
            url: The URI to parse, either as a string or a :class:`yarl.URL` instance.

        Returns:
            The parsed data, or ``None`` if parsing failed.
        """
        try:
            return cls.parse(url)
        except ValueError:
            return None

    @classmethod
    def parse(cls, url: str | URL) -> MatrixURI:
        """
        Parse a ``matrix:`` URI or ``https://matrix.to`` URL into parts.

        Args:
            url: The URI to parse, either as a string or a :class:`yarl.URL` instance.

        Returns:
            The parsed data.

        Raises:
            ValueError: if yarl fails to parse the given URL string.
            MatrixURIError: if the URL isn't valid in the Matrix spec.

        Examples:
            >>> from mautrix.types import MatrixURI
            >>> MatrixURI.parse("https://matrix.to/#/@user:example.com").user_id
            '@user:example.com'
            >>> MatrixURI.parse("https://matrix.to/#/#room:example.com/$abc123").event_id
            '$abc123'
            >>> MatrixURI.parse("matrix:r/room:example.com/e/abc123").event_id
            '$abc123'
        """
        url = URL(url)
        if url.scheme == "matrix":
            return cls._parse_matrix_uri(url)
        elif url.scheme == "https" and url.host == "matrix.to":
            return cls._parse_matrix_to_url(url)
        else:
            raise MatrixURIError("Invalid URI (not matrix: nor https://matrix.to)")

    @classmethod
    def _parse_matrix_to_url(cls, url: URL) -> MatrixURI:
        path, *rest = url.raw_fragment.split("?", 1)
        path_parts = path.split("/")
        if len(path_parts) < 2:
            raise MatrixURIError("matrix.to URL doesn't have enough parts")
        # The first component is the blank part between the # and /
        if path_parts[0] != "":
            raise MatrixURIError("first component of matrix.to URL is not empty as expected")
        query = urllib.parse.parse_qs(rest[0] if len(rest) > 0 else "")
        uri = cls()
        part1 = urllib.parse.unquote(path_parts[1])
        if len(part1) < 2:
            raise MatrixURIError(f"Invalid first entity '{part1}' in matrix.to URL")
        try:
            uri._part1 = _PathPart.from_mxid(part1)
        except KeyError as e:
            raise MatrixURIError(
                f"Invalid sigil '{part1[0]}' in first entity of matrix.to URL"
            ) from e
        if len(path_parts) > 2 and len(path_parts[2]) > 0:
            part2 = urllib.parse.unquote(path_parts[2])
            if len(part2) < 2:
                raise MatrixURIError(f"Invalid second entity '{part2}' in matrix.to URL")
            try:
                uri._part2 = _PathPart.from_mxid(part2)
            except KeyError as e:
                raise MatrixURIError(
                    f"Invalid sigil '{part2[0]}' in second entity of matrix.to URL"
                ) from e
        uri.via = query.get("via", None)
        try:
            uri.action = URIAction(query["action"])
        except KeyError:
            pass
        return uri

    @classmethod
    def _parse_matrix_uri(cls, url: URL) -> MatrixURI:
        components = url.raw_path.split("/")
        if len(components) < 2:
            raise MatrixURIError("URI doesn't contain enough parts")
        try:
            type1 = IdentifierType.from_uri_type_qualifier(components[0])
        except KeyError as e:
            raise MatrixURIError(
                f"Invalid type qualifier '{components[0]}' in first entity of matrix: URI"
            ) from e
        if not components[1]:
            raise MatrixURIError("Identifier in first entity of matrix: URI is empty")
        uri = cls()
        uri._part1 = _PathPart(type1, components[1])
        if len(components) >= 3 and components[2]:
            try:
                type2 = IdentifierType.from_uri_type_qualifier(components[2])
            except KeyError as e:
                raise MatrixURIError(
                    f"Invalid type qualifier '{components[2]}' in second entity of matrix: URI"
                ) from e
            if len(components) < 4 or not components[3]:
                raise MatrixURIError("Identifier in second entity of matrix: URI is empty")
            uri._part2 = _PathPart(type2, components[3])
        uri.via = url.query.getall("via", None)
        try:
            uri.action = URIAction(url.query["action"])
        except KeyError:
            pass
        return uri

    @property
    def user_id(self) -> UserID | None:
        """
        Get the user ID from this parsed URI.

        Returns:
            The user ID in this URI, or ``None`` if this is not a link to a user.
        """
        if self._part1.type == IdentifierType.USER:
            return UserID(self._part1.mxid)
        return None

    @property
    def room_id(self) -> RoomID | None:
        """
        Get the room ID from this parsed URI.

        Returns:
            The room ID in this URI, or ``None`` if this is not a link to a room (or event).
        """
        if self._part1.type == IdentifierType.ROOM_ID:
            return RoomID(self._part1.mxid)
        return None

    @property
    def room_alias(self) -> RoomAlias | None:
        """
        Get the room alias from this parsed URI.

        Returns:
            The room alias in this URI, or ``None`` if this is not a link to a room (or event).
        """
        if self._part1.type == IdentifierType.ROOM_ALIAS:
            return RoomAlias(self._part1.mxid)
        return None

    @property
    def event_id(self) -> EventID | None:
        """
        Get the event ID from this parsed URI.

        Returns:
            The event ID in this URI, or ``None`` if this is not a link to an event in a room.
        """
        if (
            self._part2
            and (self.room_id or self.room_alias)
            and self._part2.type == IdentifierType.EVENT
        ):
            return EventID(self._part2.mxid)
        return None

    @property
    def matrix_to_url(self) -> str:
        """
        Convert this parsed URI into a ``https://matrix.to`` URL.

        Returns:
            The link as a matrix.to URL.
        """
        url = f"https://matrix.to/#/{urllib.parse.quote(self._part1.mxid)}"
        if self._part2:
            url += f"/{urllib.parse.quote(self._part2.mxid)}"
        qp = []
        if self.via:
            qp += (("via", server) for server in self.via)
        if self.action:
            qp.append(("action", self.action))
        if qp:
            url += f"?{urllib.parse.urlencode(qp)}"
        return url

    @property
    def matrix_uri(self) -> str:
        """
        Convert this parsed URI into a ``matrix:`` URI.

        Returns:
            The link as a ``matrix:`` URI.
        """
        u = _uri_base / self._part1.type.uri_type_qualifier / self._part1.identifier
        if self._part2:
            u = u / self._part2.type.uri_type_qualifier / self._part2.identifier
        if self.via:
            u = u.update_query({"via": self.via})
        if self.action:
            u = u.update_query({"action": self.action.value})
        return str(u)

    def __str__(self) -> str:
        if self.URI_BY_DEFAULT:
            return self.matrix_uri
        else:
            return self.matrix_to_url

    def __repr__(self) -> str:
        parts = ", ".join(f"{part!r}" for part in (self._part1, self._part2) if part)
        return f"MatrixURI({parts}, via={self.via!r}, action={self.action!r})"

    def __eq__(self, other: MatrixURI) -> bool:
        """
        Checks equality between two parsed Matrix URIs. The order of the via parameters is ignored,
        but otherwise everything has to match exactly.
        """
        if not isinstance(other, MatrixURI):
            return False
        return (
            self._part1 == other._part1
            and self._part2 == other._part2
            and set(self.via or []) == set(other.via or [])
            and self.action == other.action
        )
