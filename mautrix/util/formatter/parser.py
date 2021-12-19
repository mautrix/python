# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Callable, Generic, Pattern, Type, TypeVar
import re

from ...types import RoomAlias, UserID
from .formatted_string import EntityType, FormattedString
from .html_reader import HTMLNode, read_html
from .markdown_string import MarkdownString


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

    def enter_list(self) -> RecursionContext:
        return RecursionContext(strip_linebreaks=self.strip_linebreaks, ul_depth=self.ul_depth + 1)

    def enter_code_block(self) -> RecursionContext:
        return RecursionContext(strip_linebreaks=False, ul_depth=self.ul_depth)


T = TypeVar("T", bound=FormattedString)


class MatrixParser(Generic[T]):
    mention_regex: Pattern = re.compile("https://matrix.to/#/(@.+:.+)")
    room_regex: Pattern = re.compile("https://matrix.to/#/(#.+:.+)")
    block_tags: tuple[str, ...] = (
        "p",
        "pre",
        "blockquote",
        "ol",
        "ul",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "div",
        "hr",
        "table",
    )
    list_bullets: tuple[str, ...] = ("●", "○", "■", "‣")
    e: Type[EntityType] = EntityType
    fs: Type[T] = MarkdownString
    read_html: Callable[[str], HTMLNode] = read_html
    ignore_less_relevant_links: bool = True
    exclude_plaintext_attrib: str = "data-mautrix-exclude-plaintext"

    def list_bullet(self, depth: int) -> str:
        return self.list_bullets[(depth - 1) % len(self.list_bullets)] + " "

    async def list_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        ordered: bool = node.tag == "ol"
        tagged_children: list[tuple[T, str]] = await self.node_to_tagged_fstrings(node, ctx)
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
        children: list[T] = []
        for child, tag in tagged_children:
            if tag != "li":
                continue

            if ordered:
                prefix = f"{counter}. "
                counter += 1
            else:
                prefix = self.list_bullet(ctx.ul_depth)
            child = child.prepend(prefix)
            parts = child.split("\n")
            parts = parts[:1] + [part.prepend(indent) for part in parts[1:]]
            child = self.fs.join(parts, "\n")
            children.append(child)
        return self.fs.join(children, "\n")

    async def blockquote_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        msg = await self.tag_aware_parse_node(node, ctx)
        return msg.format(self.e.BLOCKQUOTE)

    async def header_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        children = await self.node_to_fstrings(node, ctx)
        length = int(node.tag[1])
        return self.fs.join(children, "").format(self.e.HEADER, size=length)

    async def basic_format_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        msg = await self.tag_aware_parse_node(node, ctx)
        if self.exclude_plaintext_attrib in node.attrib:
            return msg
        if node.tag in ("b", "strong"):
            msg = msg.format(self.e.BOLD)
        elif node.tag in ("i", "em"):
            msg = msg.format(self.e.ITALIC)
        elif node.tag in ("s", "strike", "del"):
            msg = msg.format(self.e.STRIKETHROUGH)
        elif node.tag in ("u", "ins"):
            msg = msg.format(self.e.UNDERLINE)
        return msg

    async def link_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        msg = await self.tag_aware_parse_node(node, ctx)
        href = node.attrib.get("href", "")
        if not href:
            return msg

        if href.startswith("mailto:"):
            return self.fs(href[len("mailto:") :]).format(self.e.EMAIL)

        mention = self.mention_regex.match(href)
        if mention:
            new_msg = await self.user_pill_to_fstring(msg, UserID(mention.group(1)))
            if new_msg:
                return new_msg

        room = self.room_regex.match(href)
        if room:
            new_msg = await self.room_pill_to_fstring(msg, RoomAlias(room.group(1)))
            if new_msg:
                return new_msg

        # Custom attribute to tell the parser that the link isn't relevant and
        # shouldn't be included in plaintext representation.
        if self.ignore_less_relevant_links and self.exclude_plaintext_attrib in node.attrib:
            return msg

        return await self.url_to_fstring(msg, href)

    async def url_to_fstring(self, msg: T, url: str) -> T | None:
        return msg.format(self.e.URL, url=url)

    async def user_pill_to_fstring(self, msg: T, user_id: UserID) -> T | None:
        return msg.format(self.e.USER_MENTION, user_id=user_id)

    async def room_pill_to_fstring(self, msg: T, room_alias: RoomAlias) -> T | None:
        return msg.format(self.e.ROOM_MENTION, room_alias=room_alias)

    async def custom_node_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T | None:
        return None

    async def color_to_fstring(self, node: HTMLNode, ctx: RecursionContext, color: str) -> T:
        return await self.tag_aware_parse_node(node, ctx)

    async def node_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        custom = await self.custom_node_to_fstring(node, ctx)
        if custom:
            return custom
        elif node.tag == "mx-reply":
            return self.fs("")
        elif node.tag == "blockquote":
            return await self.blockquote_to_fstring(node, ctx)
        elif node.tag == "ol":
            return await self.list_to_fstring(node, ctx)
        elif node.tag == "ul":
            return await self.list_to_fstring(node, ctx.enter_list())
        elif node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return await self.header_to_fstring(node, ctx)
        elif node.tag == "br":
            return self.fs("\n")
        elif node.tag in ("b", "strong", "i", "em", "s", "del", "u", "ins"):
            return await self.basic_format_to_fstring(node, ctx)
        elif node.tag == "a":
            return await self.link_to_fstring(node, ctx)
        elif node.tag == "p":
            return (await self.tag_aware_parse_node(node, ctx)).append("\n")
        elif node.tag in ("font", "span"):
            try:
                color = node.attrib["color"]
            except KeyError:
                try:
                    color = node.attrib["data-mx-color"]
                except KeyError:
                    color = None
            if color:
                return await self.color_to_fstring(node, ctx, color)
        elif node.tag == "pre":
            lang = ""
            try:
                if node[0].tag == "code":
                    node = node[0]
                    lang = node.attrib["class"][len("language-") :]
            except (IndexError, KeyError):
                pass
            return (await self.parse_node(node, ctx.enter_code_block())).format(
                self.e.PREFORMATTED, language=lang
            )
        elif node.tag == "code":
            return (await self.parse_node(node, ctx.enter_code_block())).format(self.e.INLINE_CODE)
        return await self.tag_aware_parse_node(node, ctx)

    async def text_to_fstring(self, text: str, ctx: RecursionContext) -> T:
        if ctx.strip_linebreaks:
            text = text.replace("\n", "")
        return self.fs(text)

    async def node_to_tagged_fstrings(
        self, node: HTMLNode, ctx: RecursionContext
    ) -> list[tuple[T, str]]:
        output = []

        if node.text:
            output.append((await self.text_to_fstring(node.text, ctx), "text"))
        for child in node:
            output.append((await self.node_to_fstring(child, ctx), child.tag))
            if child.tail:
                output.append((await self.text_to_fstring(child.tail, ctx), "text"))
        return output

    async def node_to_fstrings(self, node: HTMLNode, ctx: RecursionContext) -> list[T]:
        return [msg for (msg, tag) in await self.node_to_tagged_fstrings(node, ctx)]

    async def tag_aware_parse_node(self, node: HTMLNode, ctx: RecursionContext) -> T:
        msgs = await self.node_to_tagged_fstrings(node, ctx)
        output = self.fs()
        prev_was_block = False
        for msg, tag in msgs:
            if tag in self.block_tags:
                msg = msg.append("\n")
                if not prev_was_block:
                    msg = msg.prepend("\n")
                prev_was_block = True
            output = output.append(msg)
        return output.trim()

    async def parse_node(self, node: HTMLNode, ctx: RecursionContext) -> T:
        return self.fs.join(await self.node_to_fstrings(node, ctx))

    async def parse(self, data: str) -> T:
        msg = await self.node_to_fstring(
            self.read_html(f"<body>{data}</body>"), RecursionContext()
        )
        return msg
