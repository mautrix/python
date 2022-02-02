from mautrix.bridge.config import BaseBridgeConfig
from mautrix.util.config import ConfigUpdateHelper
from typing import Any
import os


class Config(BaseBridgeConfig):
    def __getitem__(self, key: str) -> Any:
        try:
            return os.environ[f"LOGER_VIEWER_APPSERVICE{key.replace('.', '_').upper()}"]
        except KeyError:
            return super().__getitem__(key)

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        super().do_update(helper)
