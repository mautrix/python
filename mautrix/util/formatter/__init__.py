# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .parser import MatrixParser, RecursionContext
from .formatted_string import FormattedString, EntityType
from .entity_string import AbstractEntity, SemiAbstractEntity, SimpleEntity, EntityString
from .markdown_string import MarkdownString


def parse_html(input_html: str) -> str:
    return MatrixParser.parse(input_html).text
