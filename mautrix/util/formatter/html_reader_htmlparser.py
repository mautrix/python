# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Tuple

from html.parser import HTMLParser


class HTMLNode(list):
    tag: str
    text: str
    tail: str
    attrib: Dict[str, str]

    def __init__(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        super().__init__()
        self.tag = tag
        self.text = ""
        self.tail = ""
        self.attrib = dict(attrs)


class NodeifyingParser(HTMLParser):
    stack: List[HTMLNode]

    def __init__(self) -> None:
        super().__init__()
        self.stack = [HTMLNode("html", [])]

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        node = HTMLNode(tag, attrs)
        self.stack[-1].append(node)
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag == self.stack[-1].tag:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if len(self.stack[-1]) > 0:
            self.stack[-1][-1].tail += data
        else:
            self.stack[-1].text += data

    def error(self, message: str) -> None:
        pass


def read_html(data: str) -> HTMLNode:
    parser = NodeifyingParser()
    parser.feed(data)
    return parser.stack[0]
