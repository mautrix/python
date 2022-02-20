# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import List, Sequence, Union

from .formatted_string import EntityType, FormattedString


class MarkdownString(FormattedString):
    text: str

    def __init__(self, text: str = "") -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text

    def append(self, *args: Union[str, FormattedString]) -> MarkdownString:
        self.text += "".join(str(arg) for arg in args)
        return self

    def prepend(self, *args: Union[str, FormattedString]) -> MarkdownString:
        self.text = "".join(str(arg) for arg in args + (self.text,))
        return self

    def format(self, entity_type: EntityType, **kwargs) -> MarkdownString:
        if entity_type == EntityType.BOLD:
            self.text = f"**{self.text}**"
        elif entity_type == EntityType.ITALIC:
            self.text = f"_{self.text}_"
        elif entity_type == EntityType.STRIKETHROUGH:
            self.text = f"~~{self.text}~~"
        elif entity_type == EntityType.SPOILER:
            reason = kwargs.get("reason", "")
            if reason:
                self.text = f"{reason}|{self.text}"
            self.text = f"||{self.text}||"
        elif entity_type == EntityType.URL:
            if kwargs["url"] != self.text:
                self.text = f"[{self.text}]({kwargs['url']})"
        elif entity_type == EntityType.PREFORMATTED:
            self.text = f"```{kwargs['language']}\n{self.text}\n```"
        elif entity_type == EntityType.INLINE_CODE:
            self.text = f"`{self.text}`"
        elif entity_type == EntityType.BLOCKQUOTE:
            children = self.trim().split("\n")
            children = [child.prepend("> ") for child in children]
            self.text = self.join(children, "\n").text
        elif entity_type == EntityType.HEADER:
            prefix = "#" * kwargs["size"]
            self.text = f"{prefix} {self.text}"

        return self

    def trim(self) -> MarkdownString:
        self.text = self.text.strip()
        return self

    def split(self, separator, max_items: int = -1) -> List[MarkdownString]:
        return [MarkdownString(text) for text in self.text.split(separator, max_items)]

    @classmethod
    def join(
        cls, items: Sequence[Union[str, FormattedString]], separator: str = " "
    ) -> MarkdownString:
        return cls(separator.join(str(item) for item in items))
