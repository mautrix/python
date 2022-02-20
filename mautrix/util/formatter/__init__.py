# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .entity_string import AbstractEntity, EntityString, SemiAbstractEntity, SimpleEntity
from .formatted_string import EntityType, FormattedString
from .html_reader import HTMLNode, read_html
from .markdown_string import MarkdownString
from .parser import MatrixParser, RecursionContext


async def parse_html(input_html: str) -> str:
    return (await MatrixParser().parse(input_html)).text


__all__ = [
    "AbstractEntity",
    "EntityString",
    "SemiAbstractEntity",
    "SimpleEntity",
    "EntityType",
    "FormattedString",
    "HTMLNode",
    "read_html",
    "MarkdownString",
    "MatrixParser",
    "RecursionContext",
    "parse_html",
]
