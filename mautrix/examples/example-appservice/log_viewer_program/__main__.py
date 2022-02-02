from mautrix.types import UserID

from log_viewer_program.matrix import MatrixHandler
from log_viewer_program.logviewer import LogViewer
from log_viewer_program.config import Config


class LogViewerAppService(LogViewer):
    name = "logviewer-program"
    module = "log_viewer_program"
    command = "python -m log_viewer_program"
    description = "An appservice that shows in logs the events related to its users or to itself"
    version = "0.1"

    config_class = Config
    matrix_class = MatrixHandler

    config = Config
    matrix = MatrixHandler

    def preinit(self) -> None:
        super().preinit()

    async def start(self) -> None:
        await super().start()

    def prepare_stop(self) -> None:
        pass

    def is_bridge_ghost(self, user_id: UserID) -> bool:
        pass

    async def get_double_puppet(self, user_id: UserID):
        pass

    async def get_user(self, user_id: UserID, create: bool = True):
        pass


LogViewerAppService().run()
