# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Tuple, Pattern, Type, Optional, TypeVar, Generic, Callable
import re

from ...types import UserID, RoomAlias
from .formatted_string import FormattedString, EntityType
from .markdown_string import MarkdownString
from .html_reader import HTMLNode, read_html


class RecursionContext:
    strip_linebreaks: bool
    ul_depth: int
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


T = TypeVar('T', bound=FormattedString)


class MatrixParser(Generic[T]):
    mention_regex: Pattern = re.compile("https://matrix.to/#/(@.+:.+)")
    room_regex: Pattern = re.compile("https://matrix.to/#/(#.+:.+)")
    block_tags: Tuple[str, ...] = ("p", "pre", "blockquote",
                                   "ol", "ul", "li",
                                   "h1", "h2", "h3", "h4", "h5", "h6",
                                   "div", "hr", "table")
    list_bullets: Tuple[str, ...] = ("●", "○", "■", "‣")
    e: Type[EntityType] = EntityType
    fs: Type[T] = MarkdownString
    read_html: Callable[[str], HTMLNode] = read_html
    ignore_less_relevant_links: bool = True
    less_relevant_link_attrib: str = "data-mautrix-no-link"

    @classmethod
    def list_bullet(cls, depth: int) -> str:
        return cls.list_bullets[(depth - 1) % len(cls.list_bullets)] + " "

    @classmethod
    def list_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        ordered: bool = node.tag == "ol"
        tagged_children: List[Tuple[T, str]] = cls.node_to_tagged_fstrings(node, ctx)
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
        children: List[T] = []
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
            child = cls.fs.join(parts, "\n")
            children.append(child)
        return cls.fs.join(children, "\n")

    @classmethod
    def blockquote_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        msg = cls.tag_aware_parse_node(node, ctx)
        return msg.format(cls.e.BLOCKQUOTE)

    @classmethod
    def header_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        children = cls.node_to_fstrings(node, ctx)
        length = int(node.tag[1])
        return cls.fs.join(children, "").format(cls.e.HEADER, size=length)

    @classmethod
    def basic_format_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        msg = cls.tag_aware_parse_node(node, ctx)
        if node.tag in ("b", "strong"):
            msg = msg.format(cls.e.BOLD)
        elif node.tag in ("i", "em"):
            msg = msg.format(cls.e.ITALIC)
        elif node.tag in ("s", "strike", "del"):
            msg = msg.format(cls.e.STRIKETHROUGH)
        elif node.tag in ("u", "ins"):
            msg = msg.format(cls.e.UNDERLINE)
        return msg

    @classmethod
    def link_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        msg = cls.tag_aware_parse_node(node, ctx)
        href = node.attrib.get("href", "")
        if not href:
            return msg

        if href.startswith("mailto:"):
            return cls.fs(href[len("mailto:"):]).format(cls.e.EMAIL)

        mention = cls.mention_regex.match(href)
        if mention:
            new_msg = cls.user_pill_to_fstring(msg, UserID(mention.group(1)))
            if new_msg:
                return new_msg

        room = cls.room_regex.match(href)
        if room:
            new_msg = cls.room_pill_to_fstring(msg, RoomAlias(room.group(1)))
            if new_msg:
                return new_msg

        # Custom attribute to tell the parser that the link isn't relevant and
        # shouldn't be included in plaintext representation.
        if cls.ignore_less_relevant_links and node.attrib.get(cls.less_relevant_link_attrib, False):
            return msg

        return cls.url_to_fstring(msg, href)

    @classmethod
    def url_to_fstring(cls, msg: T, url: str) -> Optional[T]:
        return msg.format(cls.e.URL, url=url)

    @classmethod
    def user_pill_to_fstring(cls, msg: T, user_id: UserID) -> Optional[T]:
        return msg.format(cls.e.USER_MENTION, user_id=user_id)

    @classmethod
    def room_pill_to_fstring(cls, msg: T, room_alias: RoomAlias) -> Optional[T]:
        return msg.format(cls.e.ROOM_MENTION, room_alias=room_alias)

    @classmethod
    def custom_node_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> Optional[T]:
        return None

    @classmethod
    def node_to_fstring(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        custom = cls.custom_node_to_fstring(node, ctx)
        if custom:
            return custom
        elif node.tag == "mx-reply":
            return cls.fs("")
        elif node.tag == "blockquote":
            return cls.blockquote_to_fstring(node, ctx)
        elif node.tag == "ol":
            return cls.list_to_fstring(node, ctx)
        elif node.tag == "ul":
            return cls.list_to_fstring(node, ctx.enter_list())
        elif node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return cls.header_to_fstring(node, ctx)
        elif node.tag == "br":
            return cls.fs("\n")
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

    @classmethod
    def text_to_fstring(cls, text: str, ctx: RecursionContext) -> T:
        if ctx.strip_linebreaks:
            text = text.replace("\n", "")
        return cls.fs(text)

    @classmethod
    def node_to_tagged_fstrings(cls, node: HTMLNode, ctx: RecursionContext) -> List[Tuple[T, str]]:
        output = []

        if node.text:
            output.append((cls.text_to_fstring(node.text, ctx), "text"))
        for child in node:
            output.append((cls.node_to_fstring(child, ctx), child.tag))
            if child.tail:
                output.append((cls.text_to_fstring(child.tail, ctx), "text"))
        return output

    @classmethod
    def node_to_fstrings(cls, node: HTMLNode, ctx: RecursionContext) -> List[T]:
        return [msg for (msg, tag) in cls.node_to_tagged_fstrings(node, ctx)]

    @classmethod
    def tag_aware_parse_node(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        msgs = cls.node_to_tagged_fstrings(node, ctx)
        output = cls.fs()
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
    def parse_node(cls, node: HTMLNode, ctx: RecursionContext) -> T:
        return cls.fs.join(cls.node_to_fstrings(node, ctx))

    @classmethod
    def parse(cls, data: str) -> T:
        msg = cls.node_to_fstring(cls.read_html(f"<body>{data}</body>"), RecursionContext())
        return msg
