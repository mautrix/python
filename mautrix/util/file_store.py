# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import IO, Any, Protocol
from abc import ABC, abstractmethod
from pathlib import Path
import json
import pickle
import time


class Filer(Protocol):
    def dump(self, obj: Any, file: IO) -> None:
        pass

    def load(self, file: IO) -> Any:
        pass


class FileStore(ABC):
    path: str | Path | IO
    filer: Filer
    binary: bool
    save_interval: float
    _last_save: float

    def __init__(
        self,
        path: str | Path | IO,
        filer: Filer | None = None,
        binary: bool = True,
        save_interval: float = 60.0,
    ) -> None:
        self.path = path
        self.filer = filer or (pickle if binary else json)
        self.binary = binary
        self.save_interval = save_interval
        self._last_save = time.monotonic()

    @abstractmethod
    def serialize(self) -> Any:
        pass

    @abstractmethod
    def deserialize(self, data: Any) -> None:
        pass

    def _save(self) -> None:
        if isinstance(self.path, IO):
            file = self.path
            close = False
        else:
            file = open(self.path, "wb" if self.binary else "w")
            close = True
        try:
            self.filer.dump(self.serialize(), file)
        finally:
            if close:
                file.close()

    def _load(self) -> None:
        if isinstance(self.path, IO):
            file = self.path
            close = False
        else:
            try:
                file = open(self.path, "rb" if self.binary else "r")
            except FileNotFoundError:
                return
            close = True
        try:
            self.deserialize(self.filer.load(file))
        finally:
            if close:
                file.close()

    async def flush(self) -> None:
        self._save()

    async def open(self) -> None:
        self._load()

    def _time_limited_flush(self) -> None:
        if self._last_save + self.save_interval < time.monotonic():
            self._save()
            self._last_save = time.monotonic()
