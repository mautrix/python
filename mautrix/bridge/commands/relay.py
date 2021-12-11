# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from mautrix.types import EventID

from .handler import SECTION_RELAY, CommandEvent, command_handler


@command_handler(
    needs_auth=True,
    management_only=False,
    name="set-relay",
    help_section=SECTION_RELAY,
    help_text="Relay messages in this room through your account.",
    is_enabled_for=lambda evt: evt.config["bridge.relay.enabled"],
)
async def set_relay(evt: CommandEvent) -> EventID:
    if not evt.is_portal:
        return await evt.reply("This is not a portal room.")
    await evt.portal.set_relay_user(evt.sender)
    return await evt.reply(
        "Messages from non-logged-in users in this room will now be bridged "
        "through your account."
    )


@command_handler(
    needs_auth=True,
    management_only=False,
    name="unset-relay",
    help_section=SECTION_RELAY,
    help_text="Stop relaying messages in this room.",
    is_enabled_for=lambda evt: evt.config["bridge.relay.enabled"],
)
async def unset_relay(evt: CommandEvent) -> EventID:
    if not evt.is_portal:
        return await evt.reply("This is not a portal room.")
    elif not evt.portal.has_relay:
        return await evt.reply("This room does not have a relay user set.")
    await evt.portal.set_relay_user(None)
    return await evt.reply("Messages from non-logged-in users will no longer be bridged.")
