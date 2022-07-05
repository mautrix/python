# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.errors import IntentError, MatrixRequestError, MForbidden
from mautrix.types import ContentURI, EventID, UserID

from ... import bridge as br
from .handler import SECTION_ADMIN, CommandEvent, command_handler


@command_handler(
    needs_admin=True,
    needs_auth=False,
    name="set-pl",
    help_section=SECTION_ADMIN,
    help_args="[_mxid_] <_level_>",
    help_text="Set a temporary power level without affecting the remote platform.",
)
async def set_power_level(evt: CommandEvent) -> EventID:
    try:
        user_id = UserID(evt.args[0])
    except IndexError:
        return await evt.reply(f"**Usage:** `$cmdprefix+sp set-pl [mxid] <level>`")

    if user_id.startswith("@"):
        evt.args.pop(0)
    else:
        user_id = evt.sender.mxid

    try:
        level = int(evt.args[0])
    except (KeyError, IndexError):
        return await evt.reply("**Usage:** `$cmdprefix+sp set-pl [mxid] <level>`")
    except ValueError:
        return await evt.reply("The level must be an integer.")
    levels = await evt.main_intent.get_power_levels(evt.room_id, ignore_cache=True)
    levels.users[user_id] = level
    try:
        return await evt.main_intent.set_power_levels(evt.room_id, levels)
    except MForbidden as e:
        await evt.reply(f"I don't seem to have permission to update power levels: {e.message}")
    except (MatrixRequestError, IntentError):
        evt.log.exception("Failed to update power levels")
        return await evt.reply("Failed to update power levels (see logs for more details)")


async def _get_mxid_param(
    evt: CommandEvent, args: str
) -> tuple[br.BasePuppet | None, EventID | None]:
    try:
        user_id = UserID(evt.args[0])
    except IndexError:
        return None, await evt.reply(f"**Usage:** `$cmdprefix+sp {evt.command} {args}`")

    if user_id.startswith("@") and ":" in user_id:
        # TODO support parsing mention pills instead of requiring a plaintext mxid
        puppet = await evt.bridge.get_puppet(user_id)
        if not puppet:
            return None, await evt.reply("The given user ID is not a valid ghost user.")
        evt.args.pop(0)
        return puppet, None
    elif evt.is_portal and (puppet := await evt.portal.get_dm_puppet()):
        return puppet, None
    return None, await evt.reply(
        "This is not a private chat portal, you must pass a user ID explicitly."
    )


@command_handler(
    needs_admin=True,
    needs_auth=False,
    name="set-avatar",
    help_section=SECTION_ADMIN,
    help_args="[_mxid_] <_mxc:// uri_>",
    help_text="Set an avatar for a ghost user.",
)
async def set_ghost_avatar(evt: CommandEvent) -> EventID | None:
    puppet, err = await _get_mxid_param(evt, "[mxid] <mxc:// URI>")
    if err:
        return err

    try:
        mxc_uri = ContentURI(evt.args[0])
    except IndexError:
        return await evt.reply("**Usage:** `$cmdprefix+sp set-avatar [mxid] <mxc_uri>`")
    if not mxc_uri.startswith("mxc://"):
        return await evt.reply("The avatar URL must start with `mxc://`")

    try:
        return await puppet.default_mxid_intent.set_avatar_url(mxc_uri)
    except (MatrixRequestError, IntentError):
        evt.log.exception("Failed to set avatar.")
        return await evt.reply("Failed to set avatar (see logs for more details).")


@command_handler(
    needs_admin=True,
    needs_auth=False,
    name="remove-avatar",
    help_section=SECTION_ADMIN,
    help_args="[_mxid_]",
    help_text="Remove the avatar for a ghost user.",
)
async def remove_ghost_avatar(evt: CommandEvent) -> EventID | None:
    puppet, err = await _get_mxid_param(evt, "[mxid]")
    if err:
        return err
    try:
        return await puppet.default_mxid_intent.set_avatar_url(ContentURI(""))
    except (MatrixRequestError, IntentError):
        evt.log.exception("Failed to remove avatar.")
        return await evt.reply("Failed to remove avatar (see logs for more details).")


@command_handler(
    needs_admin=True,
    needs_auth=False,
    name="set-displayname",
    help_section=SECTION_ADMIN,
    help_args="[_mxid_] <_displayname_>",
    help_text="Set the display name for a ghost user.",
)
async def set_ghost_display_name(evt: CommandEvent) -> EventID | None:
    puppet, err = await _get_mxid_param(evt, "[mxid] <displayname>")
    if err:
        return err
    try:
        return await puppet.default_mxid_intent.set_displayname(" ".join(evt.args))
    except (MatrixRequestError, IntentError):
        evt.log.exception("Failed to set display name.")
        return await evt.reply("Failed to set display name (see logs for more details).")


@command_handler(
    needs_admin=True,
    needs_auth=False,
    name="remove-displayname",
    help_section=SECTION_ADMIN,
    help_args="[_mxid_]",
    help_text="Remove the display name for a ghost user.",
)
async def remove_ghost_display_name(evt: CommandEvent) -> EventID | None:
    puppet, err = await _get_mxid_param(evt, "[mxid]")
    if err:
        return err
    try:
        return await puppet.default_mxid_intent.set_displayname("")
    except (MatrixRequestError, IntentError):
        evt.log.exception("Failed to remove display name.")
        return await evt.reply("Failed to remove display name (see logs for more details).")
