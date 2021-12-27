import asyncio
from markdown import markdown

from mautrix.client import ClientAPI

user_id = "@admin:example.com"
base_url = "https://example.com"
token = "syt_123_456"

client = ClientAPI(user_id, base_url=base_url, token=token)


async def send_message_to_room(
    room_id: str, message: str, notice: bool = False, markdown_convert: bool = False
) -> None:

    msgtype = "m.notice" if notice else "m.text"

    content = {
        "formatted_body": None,
        "body": message,
        "msgtype": msgtype,
    }

    if markdown_convert:
        content["formatted_body"] = markdown(message)

    await client.send_message(room_id, content=content)


loop = asyncio.get_event_loop()
loop.run_until_complete(
    send_message_to_room(
        room_id="!foo:example.com",
        message="Hello Mau! 🐈️",
    )
)
