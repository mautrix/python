# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Callable, Generic, Type, TypeVar
import re

from ...types import EventID, MatrixURI, RoomAlias, RoomID, UserID
from .formatted_string import EntityType, FormattedString
from .html_reader import HTMLNode, read_html
from .markdown_string import MarkdownString


class RecursionContext:
    preserve_whitespace: bool
    ul_depth: int
    _inited: bool

    def __init__(self, preserve_whitespace: bool = False, ul_depth: int = 0) -> None:
        self.preserve_whitespace = preserve_whitespace
        self.ul_depth = ul_depth
        self._inited = True

    def __setattr__(self, key: str, value: Any) -> None:
        if getattr(self, "_inited", False) is True:
            raise TypeError("'RecursionContext' object is immutable")
        super(RecursionContext, self).__setattr__(key, value)

    def enter_list(self) -> RecursionContext:
        return RecursionContext(
            preserve_whitespace=self.preserve_whitespace, ul_depth=self.ul_depth + 1
        )

    def enter_code_block(self) -> RecursionContext:
        return RecursionContext(preserve_whitespace=True, ul_depth=self.ul_depth)


T = TypeVar("T", bound=FormattedString)
spaces = re.compile(r"\s+")
space = " "


class MatrixParser(Generic[T]):
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
    read_html: Callable[[str], HTMLNode] = staticmethod(read_html)
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
        indent: str = (indent_length + 2) * " "
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

    async def hr_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        return self.fs("---")

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

        matrix_uri = MatrixURI.try_parse(href)
        if matrix_uri:
            if matrix_uri.user_id:
                new_msg = await self.user_pill_to_fstring(msg, matrix_uri.user_id)
            elif matrix_uri.event_id:
                new_msg = await self.event_link_to_fstring(
                    msg, matrix_uri.room_id or matrix_uri.room_alias, matrix_uri.event_id
                )
            elif matrix_uri.room_alias:
                new_msg = await self.room_pill_to_fstring(msg, matrix_uri.room_alias)
            elif matrix_uri.room_id:
                new_msg = await self.room_id_link_to_fstring(msg, matrix_uri.room_id)
            else:
                new_msg = None
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
        return None

    async def room_id_link_to_fstring(self, msg: T, room_id: RoomID) -> T | None:
        return None

    async def event_link_to_fstring(
        self, msg: T, room: RoomID | RoomAlias, event_id: EventID
    ) -> T | None:
        return None

    async def img_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        return self.fs(node.attrib.get("alt") or node.attrib.get("title") or "")

    async def custom_node_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T | None:
        return None

    async def color_to_fstring(self, msg: T, color: str) -> T:
        return msg.format(self.e.COLOR, color=color)

    async def spoiler_to_fstring(self, msg: T, reason: str) -> T:
        return msg.format(self.e.SPOILER, reason=reason)

    async def node_to_fstring(self, node: HTMLNode, ctx: RecursionContext) -> T:
        custom = await self.custom_node_to_fstring(node, ctx)
        if custom:
            return custom
        elif node.tag == "mx-reply":
            return self.fs("")
        elif node.tag == "blockquote":
            return await self.blockquote_to_fstring(node, ctx)
        elif node.tag == "hr":
            return await self.hr_to_fstring(node, ctx)
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
        elif node.tag == "img":
            return await self.img_to_fstring(node, ctx)
        elif node.tag == "p":
            return (await self.tag_aware_parse_node(node, ctx)).append("\n")
        elif node.tag in ("font", "span"):
            msg = await self.tag_aware_parse_node(node, ctx)
            try:
                spoiler = node.attrib["data-mx-spoiler"]
            except KeyError:
                pass
            else:
                msg = await self.spoiler_to_fstring(msg, spoiler)

            try:
                color = node.attrib["color"]
            except KeyError:
                try:
                    color = node.attrib["data-mx-color"]
                except KeyError:
                    color = None
            if color:
                msg = await self.color_to_fstring(msg, color)
            return msg
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

    async def text_to_fstring(
        self, text: str, ctx: RecursionContext, strip_leading_whitespace: bool = False
    ) -> T:
        if not ctx.preserve_whitespace:
            text = spaces.sub(space, text.lstrip() if strip_leading_whitespace else text)
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
                # For text following a block tag, the leading whitespace is meaningless (there'll
                # be a newline added later), but for other tags it can be interpreted as a space.
                text = await self.text_to_fstring(
                    child.tail, ctx, strip_leading_whitespace=child.tag in self.block_tags
                )
                output.append((text, "text"))
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
