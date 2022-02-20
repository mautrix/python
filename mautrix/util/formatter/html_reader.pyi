# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
class HTMLNode(list[HTMLNode]):
    tag: str
    text: str
    tail: str
    attrib: dict[str, str]
    def __init__(self, tag: str, attrs: list[tuple[str, str]]) -> None: ...

def read_html(data: str) -> HTMLNode: ...
