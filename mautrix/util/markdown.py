# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import commonmark


class HtmlEscapingRenderer(commonmark.HtmlRenderer):
    def __init__(self, allow_html: bool = False):
        super().__init__()
        self.allow_html = allow_html

    def lit(self, s):
        if self.allow_html:
            return super().lit(s)
        return super().lit(s.replace("<", "&lt;").replace(">", "&gt;"))

    def image(self, node, entering):
        prev = self.allow_html
        self.allow_html = True
        super().image(node, entering)
        self.allow_html = prev


md_parser = commonmark.Parser()
yes_html_renderer = commonmark.HtmlRenderer()
no_html_renderer = HtmlEscapingRenderer()


def render(message: str, allow_html: bool = False) -> str:
    parsed = md_parser.parse(message)
    if allow_html:
        return yes_html_renderer.render(parsed)
    else:
        return no_html_renderer.render(parsed)
