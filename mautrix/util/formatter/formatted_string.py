# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Sequence
from abc import ABC, abstractmethod
from enum import Enum, auto


class EntityType(Enum):
    """EntityType is a Matrix formatting entity type."""

    BOLD = auto()
    ITALIC = auto()
    STRIKETHROUGH = auto()
    UNDERLINE = auto()
    URL = auto()
    EMAIL = auto()
    USER_MENTION = auto()
    ROOM_MENTION = auto()
    PREFORMATTED = auto()
    INLINE_CODE = auto()
    BLOCKQUOTE = auto()
    HEADER = auto()
    COLOR = auto()
    SPOILER = auto()


class FormattedString(ABC):
    """FormattedString is an abstract HTML parsing target."""

    @abstractmethod
    def append(self, *args: str | FormattedString) -> FormattedString:
        """
        Append strings to this FormattedString.

        This method may mutate the source object, but it is not required to do so.
        Make sure to always use the return value when mutating and to duplicate strings if you don't
        want the original to change.

        Args:
            *args: The strings to append.

        Returns:
            A FormattedString that is a concatenation of this string and the given strings.
        """
        pass

    @abstractmethod
    def prepend(self, *args: str | FormattedString) -> FormattedString:
        """
        Prepend strings to this FormattedString.

        This method may mutate the source object, but it is not required to do so.
        Make sure to always use the return value when mutating and to duplicate strings if you don't
        want the original to change.

        Args:
            *args: The strings to prepend.

        Returns:
            A FormattedString that is a concatenation of the given strings and this string.
        """
        pass

    @abstractmethod
    def format(self, entity_type: EntityType, **kwargs) -> FormattedString:
        """
        Apply formatting to this FormattedString.

        This method may mutate the source object, but it is not required to do so.
        Make sure to always use the return value when mutating and to duplicate strings if you don't
        want the original to change.

        Args:
            entity_type: The type of formatting to apply to this string.
            **kwargs: Additional metadata required by the formatting type.

        Returns:
            A FormattedString with the given formatting applied.
        """
        pass

    @abstractmethod
    def trim(self) -> FormattedString:
        """
        Trim surrounding whitespace from this FormattedString.

        This method may mutate the source object, but it is not required to do so.
        Make sure to always use the return value when mutating and to duplicate strings if you don't
        want the original to change.

        Returns:
            A FormattedString without surrounding whitespace.
        """
        pass

    @abstractmethod
    def split(self, separator, max_items: int = -1) -> list[FormattedString]:
        """
        Split this FormattedString by the given separator.

        Args:
            separator: The separator to split by.
            max_items: The maximum number of items to return. If the limit is reached, the remaining
                       string will be returned as one even if it contains the separator.

        Returns:
            The split strings.
        """
        pass

    @classmethod
    def concat(cls, *args: str | FormattedString) -> FormattedString:
        """
        Concatenate many FormattedStrings.

        Args:
            *args: The strings to concatenate.

        Returns:
            A FormattedString that is a concatenation of the given strings.
        """
        return cls.join(items=args, separator="")

    @classmethod
    @abstractmethod
    def join(cls, items: Sequence[str | FormattedString], separator: str = " ") -> FormattedString:
        """
        Join a list of FormattedStrings with the given separator.

        Args:
            items: The strings to join.
            separator: The separator to join them with.

        Returns:
            A FormattedString that is a combination of the given strings with the given separator
            between each one.
        """
        pass
