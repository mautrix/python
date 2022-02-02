from typing import TYPE_CHECKING
from mautrix.types import Event


from mautrix.bridge import BaseMatrixHandler

if TYPE_CHECKING:
    from .__main__ import LogViewerAppService


class MatrixHandler(BaseMatrixHandler):
    def __init__(self, bridge: "LogViewerAppService") -> None:
        prefix, suffix = bridge.config["bridge.username_template"].format(userid=":").split(":")
        homeserver = bridge.config["homeserver.domain"]
        self.user_id_prefix = f"@{prefix}"
        self.user_id_suffix = f"{suffix}:{homeserver}"

        super().__init__(bridge=bridge)

    async def handle_event(self, evt: Event) -> None:
        self.log.debug(f"Watching the event: {evt}")
