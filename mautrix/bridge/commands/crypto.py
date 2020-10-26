# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from .handler import (command_handler, CommandEvent, SECTION_ADMIN)


@command_handler(needs_admin=True, needs_auth=False, help_section=SECTION_ADMIN,
                 help_text="Reset the bridge's megolm session in this room")
async def discard_megolm_session(evt: CommandEvent) -> None:
    if not evt.bridge.matrix.e2ee:
        await evt.reply("End-to-bridge encryption is not enabled on this bridge instance")
        return
    await evt.bridge.matrix.e2ee.crypto_store.remove_outbound_group_session(evt.room_id)
    await evt.reply("Successfully removed outbound group session for this room")
