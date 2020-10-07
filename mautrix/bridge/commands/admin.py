# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from mautrix.types import EventID

from mautrix.errors import (MatrixRequestError, IntentError)

from .handler import (command_handler, CommandEvent, SECTION_ADMIN)


@command_handler(needs_admin=True, needs_auth=False, name="set-pl",
                 help_section=SECTION_ADMIN,
                 help_args="<_level_> [_mxid_]",
                 help_text="Set a temporary power level without affecting the bridge.")
async def set_power_level(evt: CommandEvent) -> EventID:
    try:
        level = int(evt.args[0])
    except (KeyError, IndexError):
        return await evt.reply("**Usage:** `$cmdprefix+sp set-pl <level> [mxid]`")
    except ValueError:
        return await evt.reply("The level must be an integer.")
    if evt.is_portal:
        portal = await evt.processor.bridge.get_portal(evt.room_id)
        levels = await portal.main_intent.get_power_levels(evt.room_id)
    else:
        levels = await evt.az.intent.get_power_levels(evt.room_id)
    mxid = evt.args[1] if len(evt.args) > 1 else evt.sender.mxid
    levels.users[mxid] = level
    try:
        if evt.is_portal:
            return await portal.main_intent.set_power_levels(evt.room_id, levels)
        else:
            return await evt.az.intent.set_power_levels(evt.room_id, levels)
    except (MatrixRequestError, IntentError):
        evt.log.exception("Failed to set power level.")
        return await evt.reply("Failed to set power level.")
