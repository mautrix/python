# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from copy import copy
from logging import Formatter, LogRecord

PREFIX = "\033["
RESET = PREFIX + "0m"
MAU_COLOR = PREFIX + "32m"  # green
AIOHTTP_COLOR = PREFIX + "36m"  # cyan
MXID_COLOR = PREFIX + "33m"  # yellow

LEVEL_COLORS = {
    "DEBUG": "37m",  # white
    "INFO": "36m",  # cyan
    "WARNING": "33;1m",  # yellow
    "ERROR": "31;1m",  # red
    "CRITICAL": f"37;1m{PREFIX}41m",  # white on red bg
}

LEVELNAME_OVERRIDE = {
    name: f"{PREFIX}{color}{name}{RESET}" for name, color in LEVEL_COLORS.items()
}


class ColorFormatter(Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _color_name(self, module: str) -> str:
        as_api = "mau.as.api"
        if module.startswith(as_api):
            return f"{MAU_COLOR}{as_api}{RESET}.{MXID_COLOR}{module[len(as_api) + 1:]}{RESET}"
        elif module.startswith("mau."):
            try:
                next_dot = module.index(".", len("mau."))
                return (
                    f"{MAU_COLOR}{module[:next_dot]}{RESET}"
                    f".{MXID_COLOR}{module[next_dot+1:]}{RESET}"
                )
            except ValueError:
                return MAU_COLOR + module + RESET
        elif module.startswith("aiohttp"):
            return AIOHTTP_COLOR + module + RESET
        return module

    def format(self, record: LogRecord):
        colored_record: LogRecord = copy(record)
        colored_record.name = self._color_name(record.name)
        colored_record.levelname = LEVELNAME_OVERRIDE.get(record.levelname, record.levelname)
        return super().format(colored_record)
