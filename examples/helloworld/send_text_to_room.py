import asyncio
from markdown import markdown

from mautrix.client import ClientAPI
from mautrix.types.event.message import Format, TextMessageEventContent

# The user_id you have in your homeserver
user_id = "@admin:example.com"

# You homeserver addres
base_url = "https://example.com"

# The generated token for your user on the homeserver
token = "syt_123_456"

# Create a client that will be connected to your homeserver
client = ClientAPI(user_id, base_url=base_url, token=token)


async def send_message_to_room(room_id: str, message: str, notice: bool = False) -> None:

    # Defines whether the message is a notice or a text message
    msgtype = "m.notice" if notice else "m.text"

    # We create the content to make the message sending request
    content = TextMessageEventContent(
        msgtype=msgtype,
        body=message,
        format=Format.HTML,
        formatted_body=markdown(message),
    )

    # With the client, we call the method send_message and send the content
    await client.send_message(room_id, content=content)


loop = asyncio.get_event_loop()
loop.run_until_complete(
    send_message_to_room(
        room_id="!foo:example.com",
        message="Hello Mau! 🐈️",
    )
)
