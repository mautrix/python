# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from mautrix.client import Client
from ..custom_puppet import (OnlyLoginSelf, OnlyLoginTrustedDomain, InvalidAccessToken,
                             HomeserverURLNotFound, AutologinError)
from .handler import SECTION_AUTH, CommandEvent, command_handler


@command_handler(needs_auth=True, management_only=True, help_args="<_access token_>",
                 help_section=SECTION_AUTH, help_text="Enable double puppeting")
async def login_matrix(evt: CommandEvent) -> None:
    if len(evt.args) == 0:
        await evt.reply("**Usage:** `$cmdprefix+sp login-matrix <access token>`")
        return
    try:
        puppet = await evt.sender.get_puppet()
    except NotImplementedError:
        await evt.reply("This bridge has not implemented the login-matrix command")
        return
    _, homeserver = Client.parse_mxid(evt.sender.mxid)
    try:
        await puppet.switch_mxid(evt.args[0], evt.sender.mxid)
        await evt.reply("Successfully enabled double puppeting")
    except OnlyLoginSelf:
        await evt.reply("You may only enable double puppeting with your own Matrix account")
    except OnlyLoginTrustedDomain:
        await evt.reply(f"This bridge does not allow double puppeting from {homeserver}")
    except HomeserverURLNotFound:
        await evt.reply(f"Unable to find the base URL for {homeserver}. Please ensure a client"
                        " .well-known file is set up, or ask the bridge administrator to add the"
                        " homeserver URL to the bridge config.")
    except AutologinError as e:
        await evt.reply(f"Failed to create an access token: {e}")
    except InvalidAccessToken:
        await evt.reply("Invalid access token")


@command_handler(needs_auth=True, management_only=True, help_section=SECTION_AUTH,
                 help_text="Disable double puppeting")
async def logout_matrix(evt: CommandEvent) -> None:
    try:
        puppet = await evt.sender.get_puppet()
    except NotImplementedError:
        await evt.reply("This bridge has not implemented the logout-matrix command")
        return
    if not puppet or not puppet.is_real_user:
        await evt.reply("You don't have double puppeting enabled")
        return
    await puppet.switch_mxid(None, None)
    await evt.reply("Successfully disabled double puppeting")
