# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
try:
    from .html_reader_lxml import HTMLNode, read_html
except ImportError:
    from .html_reader_htmlparser import HTMLNode, read_html
