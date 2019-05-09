# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from logging import Formatter, LogRecord
from copy import copy

PREFIX = "\033["

LEVEL_COLORS = {
    "DEBUG": "37m",  # white
    "INFO": "36m",  # cyan
    "WARNING": "33;1m",  # yellow
    "ERROR": "31;1m",  # red
    "CRITICAL": f"37;1m{PREFIX}41m",  # white on red bg
}

MAU_COLOR = PREFIX + "32;1m"  # green
AIOHTTP_COLOR = PREFIX + "36;1m"  # cyan
MXID_COLOR = PREFIX + "33m"  # yellow

RESET = "\033[0m"


class ColorFormatter(Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _color_name(self, module: str) -> str:
        if module.startswith("mau.as"):
            return MAU_COLOR + module + RESET
        elif module.startswith("mau."):
            try:
                next_dot = module.index(".", len("mau."))
                return (MAU_COLOR + module[:next_dot] + RESET
                        + "." + MXID_COLOR + module[next_dot + 1:] + RESET)
            except ValueError:
                return MAU_COLOR + module + RESET
        elif module.startswith("aiohttp"):
            return AIOHTTP_COLOR + module + RESET
        return module

    def format(self, record: LogRecord):
        colored_record: LogRecord = copy(record)
        colored_record.name = self._color_name(record.name)
        try:
            levelname = record.levelname
            colored_record.levelname = PREFIX + LEVEL_COLORS[levelname] + levelname + RESET
        except KeyError:
            pass
        return super().format(colored_record)
