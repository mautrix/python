# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Tuple, Pattern, Type, Optional
import re

from ...types import UserID, RoomAlias
from .formatted_string import FormattedString, EntityType
from .html_reader import HTMLNode, read_html


class RecursionContext:
    strip_linebreaks: bool
    ul_depth: bool
    _inited: bool

    def __init__(self, strip_linebreaks: bool = True, ul_depth: int = 0):
        self.strip_linebreaks = strip_linebreaks
        self.ul_depth = ul_depth
        self._inited = True

    def __setattr__(self, key, value):
        if getattr(self, "_inited", False) is True:
            raise TypeError("'RecursionContext' object is immutable")
        super(RecursionContext, self).__setattr__(key, value)

    def enter_list(self) -> 'RecursionContext':
        return RecursionContext(strip_linebreaks=self.strip_linebreaks, ul_depth=self.ul_depth + 1)

    def enter_code_block(self) -> 'RecursionContext':
        return RecursionContext(strip_linebreaks=False, ul_depth=self.ul_depth)


class MatrixParser:
    mention_regex: Pattern = re.compile("https://matrix.to/#/(@.+:.+)")
    room_regex: Pattern = re.compile("https://matrix.to/#/(#.+:.+)")
    block_tags: Tuple[str, ...] = ("p", "pre", "blockquote",
                                   "ol", "ul", "li",
                                   "h1", "h2", "h3", "h4", "h5", "h6",
                                   "div", "hr", "table")
    list_bullets: Tuple[str, ...] = ("●", "○", "■", "‣")
    e: Type[EntityType] = EntityType

    @classmethod
    def list_bullet(cls, depth: int) -> str:
        return cls.list_bullets[(depth - 1) % len(cls.list_bullets)] + " "

    @classmethod
    def list_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> FormattedString:
        ordered: bool = node.tag == "ol"
        tagged_children: List[Tuple[FormattedString, str]] = cls.node_to_tagged_fstrings(node, ctx)
        counter: int = 1
        indent_length: int = 0
        if ordered:
            try:
                counter = int(node.attrib.get("start", "1"))
            except ValueError:
                counter = 1

            longest_index = counter - 1 + len(tagged_children)
            indent_length = len(str(longest_index))
        indent: str = (indent_length + 4) * " "
        children: List[FormattedString] = []
        for child, tag in tagged_children:
            if tag != "li":
                continue

            if ordered:
                prefix = f"{counter}. "
                counter += 1
            else:
                prefix = cls.list_bullet(ctx.ul_depth)
            child = child.prepend(prefix)
            parts = child.split("\n")
            parts = parts[:1] + [part.prepend(indent) for part in parts[1:]]
            child = FormattedString.join(parts, "\n")
            children.append(child)
        return FormattedString.join(children, "\n")

    @classmethod
    def blockquote_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> FormattedString:
        msg = cls.tag_aware_parse_node(node, ctx)
        children = msg.trim().split("\n")
        children = [child.prepend("> ") for child in children]
        return FormattedString.join(children, "\n")

    @classmethod
    def header_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> FormattedString:
        children = cls.node_to_fstrings(node, ctx)
        length = int(node.tag[1])
        prefix = "#" * length + " "
        return FormattedString.join(children, "").prepend(prefix).format(cls.e.BOLD)

    @classmethod
    def basic_format_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> FormattedString:
        msg = cls.tag_aware_parse_node(node, ctx)
        if node.tag in ("b", "strong"):
            msg.format(cls.e.BOLD)
        elif node.tag in ("i", "em"):
            msg.format(cls.e.ITALIC)
        elif node.tag in ("s", "strike", "del"):
            msg.format(cls.e.STRIKETHROUGH)
        elif node.tag in ("u", "ins"):
            msg.format(cls.e.UNDERLINE)
        return msg

    @classmethod
    def link_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> FormattedString:
        msg = cls.tag_aware_parse_node(node, ctx)
        href = node.attrib.get("href", "")
        if not href:
            return msg

        if href.startswith("mailto:"):
            return FormattedString(href[len("mailto:"):]).format(cls.e.EMAIL)

        mention = cls.mention_regex.match(href)
        if mention:
            new_msg = cls.user_pill_to_fstring(msg, UserID(mention.group(1)))
            if new_msg:
                return new_msg

        room = cls.room_regex.match(href)
        if room:
            new_msg = cls.room_pill_to_fstring(msg, RoomAlias(mention.group(1)))
            if new_msg:
                return new_msg

        return (msg.format(cls.e.URL)
                if msg.text == href
                else msg.format(cls.e.INLINE_URL, url=href))

    @classmethod
    def user_pill_to_fstring(cls, msg: FormattedString, user_id: UserID
                             ) -> Optional[FormattedString]:
        return msg

    @classmethod
    def room_pill_to_fstring(cls, msg: FormattedString, room_alias: RoomAlias
                             ) -> Optional[FormattedString]:
        return FormattedString(room_alias)

    @classmethod
    def custom_node_to_fstring(cls, node: HTMLNode, ctx: RecursionContext
                               ) -> Optional[FormattedString]:
        return None

    @classmethod
    def node_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> FormattedString:
        custom = cls.custom_node_to_fstring(node, ctx)
        if custom:
            return custom
        elif node.tag == "blockquote":
            return cls.blockquote_to_fstring(node, ctx)
        elif node.tag == "ol":
            return cls.list_to_fstring(node, ctx)
        elif node.tag == "ul":
            return cls.list_to_fstring(node, ctx.enter_list())
        elif node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return cls.header_to_fstring(node, ctx)
        elif node.tag == "br":
            return FormattedString("\n")
        elif node.tag in ("b", "strong", "i", "em", "s", "del", "u", "ins"):
            return cls.basic_format_to_fstring(node, ctx)
        elif node.tag == "a":
            return cls.link_to_fstring(node, ctx)
        elif node.tag == "p":
            return cls.tag_aware_parse_node(node, ctx).append("\n")
        elif node.tag == "pre":
            lang = ""
            try:
                if node[0].tag == "code":
                    node = node[0]
                    lang = node.attrib["class"][len("language-"):]
            except (IndexError, KeyError):
                pass
            return cls.parse_node(node, ctx.enter_code_block()).format(cls.e.PREFORMATTED,
                                                                       language=lang)
        elif node.tag == "code":
            return cls.parse_node(node, ctx.enter_code_block()).format(cls.e.INLINE_CODE)
        return cls.tag_aware_parse_node(node, ctx)

    @staticmethod
    def text_to_fstring(text: str, ctx: RecursionContext) -> FormattedString:
        if ctx.strip_linebreaks:
            text = text.replace("\n", "")
        return FormattedString(text)

    @classmethod
    def node_to_tagged_fstrings(cls, node: HTMLNode, ctx: RecursionContext
                                ) -> List[Tuple[FormattedString, str]]:
        output = []

        if node.text:
            output.append((cls.text_to_fstring(node.text, ctx), "text"))
        for child in node:
            output.append((cls.node_to_fstring(child, ctx), child.tag))
            if child.tail:
                output.append((cls.text_to_fstring(child.tail, ctx), "text"))
        return output

    @classmethod
    def node_to_fstrings(cls, node: HTMLNode, ctx: RecursionContext
                         ) -> List[FormattedString]:
        return [msg for (msg, tag) in cls.node_to_tagged_fstrings(node, ctx)]

    @classmethod
    def tag_aware_parse_node(cls, node: HTMLNode, ctx: RecursionContext
                             ) -> FormattedString:
        msgs = cls.node_to_tagged_fstrings(node, ctx)
        output = FormattedString()
        prev_was_block = False
        for msg, tag in msgs:
            if tag in cls.block_tags:
                msg = msg.append("\n")
                if not prev_was_block:
                    msg = msg.prepend("\n")
                prev_was_block = True
            output = output.append(msg)
        return output.trim()

    @classmethod
    def parse_node(cls, node: HTMLNode, ctx: RecursionContext) -> FormattedString:
        return FormattedString.join(cls.node_to_fstrings(node, ctx))

    @classmethod
    def parse(cls, data: str) -> FormattedString:
        msg = cls.node_to_fstring(read_html(f"<body>{data}</body>"), RecursionContext())
        return msg
