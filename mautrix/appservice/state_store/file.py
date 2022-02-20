# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import IO, Any
from pathlib import Path

from mautrix.client.state_store import FileStateStore
from mautrix.util.file_store import Filer

from .memory import ASStateStore


class FileASStateStore(FileStateStore, ASStateStore):
    def __init__(
        self,
        path: str | Path | IO,
        filer: Filer | None = None,
        binary: bool = True,
        save_interval: float = 60.0,
    ) -> None:
        FileStateStore.__init__(self, path, filer, binary, save_interval)
        ASStateStore.__init__(self)

    def serialize(self) -> dict[str, Any]:
        return {
            "registered": self._registered,
            **super().serialize(),
        }

    def deserialize(self, data: dict[str, Any]) -> None:
        self._registered = data["registered"]
        super().deserialize(data)
