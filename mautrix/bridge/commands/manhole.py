# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Callable
import asyncio
import os

from attr import dataclass

from mautrix.errors import MatrixConnectionError
from mautrix.types import UserID
from mautrix.util.manhole import start_manhole

from . import SECTION_ADMIN, CommandEvent, command_handler


@dataclass
class ManholeState:
    server: asyncio.AbstractServer
    opened_by: UserID
    close: Callable[[], None]
    whitelist: set[int]


@command_handler(
    needs_auth=False,
    needs_admin=True,
    help_section=SECTION_ADMIN,
    help_text="Open a manhole into the bridge.",
    help_args="<_uid..._>",
)
async def open_manhole(evt: CommandEvent) -> None:
    if not evt.config["manhole.enabled"]:
        await evt.reply("The manhole has been disabled in the config.")
        return
    elif len(evt.args) == 0:
        await evt.reply("**Usage:** `$cmdprefix+sp open-manhole <uid...>`")
        return

    whitelist = set()
    whitelist_whitelist = evt.config["manhole.whitelist"]
    for arg in evt.args:
        try:
            uid = int(arg)
        except ValueError:
            await evt.reply(f"{arg} is not an integer.")
            return
        if whitelist_whitelist and uid not in whitelist_whitelist:
            await evt.reply(f"{uid} is not in the list of allowed UIDs.")
            return
        whitelist.add(uid)

    if evt.bridge.manhole:
        added = [uid for uid in whitelist if uid not in evt.bridge.manhole.whitelist]
        evt.bridge.manhole.whitelist |= set(added)
        if len(added) == 0:
            await evt.reply(
                f"There's an existing manhole opened by {evt.bridge.manhole.opened_by}"
                " and all the given UIDs are already whitelisted."
            )
        else:
            added_str = (
                f"{', '.join(str(uid) for uid in added[:-1])} and {added[-1]}"
                if len(added) > 1
                else added[0]
            )
            await evt.reply(
                f"There's an existing manhole opened by {evt.bridge.manhole.opened_by}"
                f". Added {added_str} to the whitelist."
            )
            evt.log.info(f"{evt.sender.mxid} added {added_str} to the manhole whitelist.")
        return

    namespace = await evt.bridge.manhole_global_namespace(evt.sender.mxid)
    banner = evt.bridge.manhole_banner(evt.sender.mxid)
    path = evt.config["manhole.path"]

    wl_list = list(whitelist)
    whitelist_str = (
        f"{', '.join(str(uid) for uid in wl_list[:-1])} and {wl_list[-1]}"
        if len(wl_list) > 1
        else wl_list[0]
    )
    evt.log.info(f"{evt.sender.mxid} opened a manhole with {whitelist_str} whitelisted.")
    server, close = await start_manhole(
        path=path, banner=banner, namespace=namespace, loop=evt.loop, whitelist=whitelist
    )
    evt.bridge.manhole = ManholeState(
        server=server, opened_by=evt.sender.mxid, close=close, whitelist=whitelist
    )
    plrl = "s" if len(whitelist) != 1 else ""
    await evt.reply(f"Opened manhole at unix://{path} with UID{plrl} {whitelist_str} whitelisted")
    await server.wait_closed()
    evt.bridge.manhole = None
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    evt.log.info(f"{evt.sender.mxid}'s manhole was closed.")
    try:
        await evt.reply("Your manhole was closed.")
    except (AttributeError, MatrixConnectionError) as e:
        evt.log.warning(f"Failed to send manhole close notification: {e}")


@command_handler(
    needs_auth=False,
    needs_admin=True,
    help_section=SECTION_ADMIN,
    help_text="Close an open manhole.",
)
async def close_manhole(evt: CommandEvent) -> None:
    if not evt.bridge.manhole:
        await evt.reply("There is no open manhole.")
        return

    opened_by = evt.bridge.manhole.opened_by
    evt.bridge.manhole.close()
    evt.bridge.manhole = None
    if opened_by != evt.sender.mxid:
        await evt.reply(f"Closed manhole opened by {opened_by}")
