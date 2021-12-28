import asyncio
from markdown import markdown

from mautrix.client import ClientAPI
from mautrix.types.event.message import Format, TextMessageEventContent

user_id = "@admin:example.com"
base_url = "https://example.com"
token = "syt_123_456"

client = ClientAPI(user_id, base_url=base_url, token=token)


async def send_message_to_room(room_id: str, message: str, notice: bool = False) -> None:

    msgtype = "m.notice" if notice else "m.text"

    content = TextMessageEventContent(
        msgtype=msgtype,
        body=message,
        format=Format.HTML,
        formatted_body=markdown(message),
    )

    await client.send_message(room_id, content=content)


loop = asyncio.get_event_loop()
loop.run_until_complete(
    send_message_to_room(
        room_id="!foo:example.com",
        message="Hello Mau! 🐈️",
    )
)
