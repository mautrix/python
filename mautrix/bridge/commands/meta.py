# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.types import EventID

from .handler import (
    SECTION_GENERAL,
    CommandEvent,
    HelpCacheKey,
    HelpSection,
    command_handler,
    command_handlers,
)


@command_handler(
    needs_auth=False, help_section=SECTION_GENERAL, help_text="Cancel an ongoing action."
)
async def cancel(evt: CommandEvent) -> EventID:
    if evt.sender.command_status:
        action = evt.sender.command_status["action"]
        evt.sender.command_status = None
        return await evt.reply(f"{action} cancelled.")
    else:
        return await evt.reply("No ongoing command.")


@command_handler(
    needs_auth=False, help_section=SECTION_GENERAL, help_text="Get the bridge version."
)
async def version(evt: CommandEvent) -> None:
    if not evt.processor.bridge:
        await evt.reply("Bridge version unknown")
    else:
        await evt.reply(
            f"[{evt.processor.bridge.name}]({evt.processor.bridge.repo_url}) "
            f"{evt.processor.bridge.markdown_version or evt.processor.bridge.version}"
        )


@command_handler(needs_auth=False)
async def unknown_command(evt: CommandEvent) -> EventID:
    return await evt.reply("Unknown command. Try `$cmdprefix+sp help` for help.")


help_cache: dict[HelpCacheKey, str] = {}


async def _get_help_text(evt: CommandEvent) -> str:
    cache_key = await evt.get_help_key()
    if cache_key not in help_cache:
        help_sections: dict[HelpSection, list[str]] = {}
        for handler in command_handlers.values():
            if (
                handler.has_help
                and handler.has_permission(cache_key)
                and handler.is_enabled_for(evt)
            ):
                help_sections.setdefault(handler.help_section, [])
                help_sections[handler.help_section].append(handler.help + "  ")
        help_sorted = sorted(help_sections.items(), key=lambda item: item[0].order)
        helps = ["#### {}\n{}\n".format(key.name, "\n".join(value)) for key, value in help_sorted]
        help_cache[cache_key] = "\n".join(helps)
    return help_cache[cache_key]


def _get_management_status(evt: CommandEvent) -> str:
    if evt.is_management:
        return "This is a management room: prefixing commands with `$cmdprefix` is not required."
    elif evt.is_portal:
        return (
            "**This is a portal room**: you must always prefix commands with `$cmdprefix`.\n"
            "Management commands will not be bridged."
        )
    return "**This is not a management room**: you must prefix commands with `$cmdprefix`."


@command_handler(
    name="help",
    needs_auth=False,
    help_section=SECTION_GENERAL,
    help_text="Show this help message.",
)
async def help_cmd(evt: CommandEvent) -> EventID:
    return await evt.reply(_get_management_status(evt) + "\n" + await _get_help_text(evt))
