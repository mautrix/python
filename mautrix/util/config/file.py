# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional
from abc import ABC
import pkgutil
import logging

from yarl import URL
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .base import BaseConfig
from .recursive_dict import RecursiveDict

yaml = YAML()
yaml.indent(4)
yaml.width = 200

log: logging.Logger = logging.getLogger("mau.util.config")


class BaseFileConfig(BaseConfig, ABC):
    def __init__(self, path: str, base_path: str) -> None:
        super().__init__()
        self._data = CommentedMap()
        self.path: str = path
        self.base_path: str = base_path

    def load(self) -> None:
        with open(self.path, 'r') as stream:
            self._data = yaml.load(stream)

    def load_base(self) -> Optional[RecursiveDict[CommentedMap]]:
        if self.base_path.startswith("pkg://"):
            url = URL(self.base_path)
            return RecursiveDict(yaml.load(pkgutil.get_data(url.host, url.path)), CommentedMap)
        try:
            with open(self.base_path, 'r') as stream:
                return RecursiveDict(yaml.load(stream), CommentedMap)
        except OSError:
            pass
        return None

    def save(self) -> None:
        try:
            with open(self.path, 'w') as stream:
                yaml.dump(self._data, stream)
        except OSError:
            log.exception(f"Failed to overwrite the config in {self.path}")
