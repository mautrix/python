# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Type, cast
import logging

TRACE = logging.TRACE = 5
logging.addLevelName(TRACE, "TRACE")

SILLY = logging.SILLY = 1
logging.addLevelName(SILLY, "SILLY")

OldLogger: Type[logging.Logger] = cast(Type[logging.Logger], logging.getLoggerClass())


class TraceLogger(OldLogger):
    def trace(self, msg, *args, **kwargs) -> None:
        self.log(TRACE, msg, *args, **kwargs)

    def silly(self, msg, *args, **kwargs) -> None:
        self.log(SILLY, msg, *args, **kwargs)

    def getChild(self, suffix: str) -> TraceLogger:
        return cast(TraceLogger, super().getChild(suffix))


logging.setLoggerClass(TraceLogger)
