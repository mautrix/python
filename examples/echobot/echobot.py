#!/usr/bin/env python3

# Copyright (c) 2022 Marc Ordinas i Llopis
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# A simple Matrix echo bot to show the usage of mautrix-python.
#
# To use it, you'll need an access token and a device ID.
# If you don't have those, first create a user (for example, 'echobot') in your homeserver. Then,
# log it in with
#      curl -XPOST -d '{"type":"m.login.password", "user":"echobot", "password":"echobot"}' \
#      http://localhost:8008/_matrix/client/v3/login
# This will return the device ID and token necessaries. Fill in the Echobot static vars and run.
#
# Once connected, invite the bot to a room and send a message starting with "!echo". You should get
# a notice from the bot.


import asyncio

from mautrix.client import Client
from mautrix.types import EventType, MessageEvent, StrippedStateEvent, Membership, \
    TextMessageEventContent, MessageType, Format


class EchoBot:
    # Change to the correct user and homeserver.
    user_id = "@echobot:localhost"
    base_url = "http://localhost:8008"

    # Fill in with the login result.
    token = "<token>"
    device_id = "<device ID>"

    def __init__(self):
        # Create the client to access Matrix.
        self.client = Client(mxid=EchoBot.user_id,
                             device_id=EchoBot.device_id,
                             base_url=EchoBot.base_url,
                             token=EchoBot.token)
        # As we aren't passing any :class:SyncStore or :class:StateStore, just ignore anything sent
        # before we connect.
        self.client.ignore_initial_sync = True
        self.client.ignore_first_sync = True

        # Register two handlers, one for room memberships (invites) and another for room messages.
        self.client.add_event_handler(EventType.ROOM_MEMBER, self.handle_invite)
        self.client.add_event_handler(EventType.ROOM_MESSAGE, self.handle_message)

    async def handle_invite(self, event: StrippedStateEvent) -> None:
        # Ignore the message if it's not an invitation for us.
        if event.state_key == self.user_id and event.content.membership == Membership.INVITE:
            # If it is, join the room.
            await self.client.join_room(event.room_id)

    async def handle_message(self, event: MessageEvent) -> None:
        if event.sender == self.user_id:
            # Ignore our own messages
            return

        if event.content.relates_to:
            # Don't echo replies to other messages
            return

        body = event.content.body
        if body.startswith("!echo"):
            response = TextMessageEventContent(
                msgtype=MessageType.NOTICE,
                body=body[5:].strip()
            )
            # If there's HTML-formatted content, echo that too
            if event.content.format == Format.HTML:
                response.format = Format.HTML
                response.formatted_body = event.content.formatted_body[5:].strip()

            # Send back the notice
            await self.client.send_message(event.room_id, response)

    async def start(self):
        print("Starting EchoBot")
        whoami = await self.client.whoami()
        print(f"\tConnected, I'm {whoami.user_id} using {whoami.device_id}")
        await self.client.start(None)


async def main():
    bot = EchoBot()
    await bot.start()


if __name__ == '__main__':
    asyncio.run(main())
