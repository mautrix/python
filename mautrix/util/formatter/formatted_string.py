# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Sequence, Union
from enum import Enum


class EntityType(Enum):
    BOLD = 1
    ITALIC = 2
    STRIKETHROUGH = 3
    UNDERLINE = 4
    URL = 5
    INLINE_URL = 6
    EMAIL = 7
    PREFORMATTED = 8
    INLINE_CODE = 9

    def apply(self, text: str, **kwargs) -> str:
        if self == EntityType.BOLD:
            return f"**{text}**"
        elif self == EntityType.ITALIC:
            return f"_{text}_"
        elif self == EntityType.STRIKETHROUGH:
            return f"~~{text}~~"
        elif self == EntityType.UNDERLINE:
            return text
        elif self == EntityType.URL:
            return text
        elif self == EntityType.INLINE_URL:
            return f"{text} ({kwargs['url']})"
        elif self == EntityType.EMAIL:
            return text
        elif self == EntityType.PREFORMATTED:
            return f"```{kwargs['language']}\n{text}\n```"
        elif self == EntityType.INLINE_CODE:
            return f"`{text}`"


class FormattedString:
    text: str

    def __init__(self, text: str = "") -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text

    def append(self, *args: Union[str, 'FormattedString']) -> 'FormattedString':
        self.text += "".join(str(arg) for arg in args)
        return self

    def prepend(self, *args: Union[str, 'FormattedString']) -> 'FormattedString':
        self.text = "".join(str(arg) for arg in args + (self.text,))
        return self

    def format(self, entity_type: EntityType, **kwargs) -> 'FormattedString':
        self.text = entity_type.apply(self.text, **kwargs)
        return self

    def trim(self) -> 'FormattedString':
        self.text = self.text.strip()
        return self

    def split(self, separator, max_items: int = 0) -> List['FormattedString']:
        return [FormattedString(text) for text in self.text.split(separator, max_items)]

    @classmethod
    def concat(cls, *args: Union[str, 'FormattedString']) -> 'FormattedString':
        return cls.join(items=args, separator="")

    @classmethod
    def join(cls, items: Sequence[Union[str, 'FormattedString']],
             separator: str = " ") -> 'FormattedString':
        return cls(separator.join(str(item) for item in items))
