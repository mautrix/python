# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any, Optional, TYPE_CHECKING

from mautrix.client.state_store import FileStateStore

from .memory import ASStateStore

if TYPE_CHECKING:
    from mautrix.util.file_store import PathLike, Filer


class FileASStateStore(FileStateStore, ASStateStore):
    def __init__(self, path: 'PathLike', filer: Optional['Filer'] = None, binary: bool = True,
                 save_interval: float = 60.0) -> None:
        FileStateStore.__init__(self, path, filer, binary, save_interval)
        ASStateStore.__init__(self)

    def serialize(self) -> Dict[str, Any]:
        return {
            "registered": self._registered,
            **super().serialize(),
        }

    def deserialize(self, data: Dict[str, Any]) -> None:
        self._registered = data["registered"]
        super().deserialize(data)
