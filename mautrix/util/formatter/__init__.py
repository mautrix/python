# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .entity_string import AbstractEntity, EntityString, SemiAbstractEntity, SimpleEntity
from .formatted_string import EntityType, FormattedString
from .markdown_string import MarkdownString
from .parser import MatrixParser, RecursionContext


async def parse_html(input_html: str) -> str:
    return (await MatrixParser().parse(input_html)).text
