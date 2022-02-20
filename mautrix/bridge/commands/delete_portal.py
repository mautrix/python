# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .handler import SECTION_ADMIN, CommandEvent, command_handler


@command_handler(
    needs_auth=False,
    needs_puppeting=False,
    needs_admin=True,
    help_section=SECTION_ADMIN,
    help_text="Remove all users from the current portal room and forget the portal.",
)
async def delete_portal(evt: CommandEvent) -> None:
    if not evt.portal:
        await evt.reply("This is not a portal room")
        return
    await evt.portal.cleanup_and_delete()


@command_handler(
    needs_auth=False,
    needs_puppeting=False,
    help_section=SECTION_ADMIN,
    help_text="Remove puppets from the current portal room and forget the portal.",
)
async def unbridge(evt: CommandEvent) -> None:
    if not evt.portal:
        await evt.reply("This is not a portal room")
        return
    await evt.portal.unbridge()
