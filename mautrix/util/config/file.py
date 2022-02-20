# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from abc import ABC
import logging
import os
import pkgutil
import tempfile

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from yarl import URL

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
        with open(self.path, "r") as stream:
            self._data = yaml.load(stream)

    def load_base(self) -> RecursiveDict[CommentedMap] | None:
        if self.base_path.startswith("pkg://"):
            url = URL(self.base_path)
            return RecursiveDict(yaml.load(pkgutil.get_data(url.host, url.path)), CommentedMap)
        try:
            with open(self.base_path, "r") as stream:
                return RecursiveDict(yaml.load(stream), CommentedMap)
        except OSError:
            pass
        return None

    def save(self) -> None:
        try:
            tf = tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".yaml", dir=os.path.dirname(self.path)
            )
        except OSError as e:
            log.warning(f"Failed to create tempfile to write updated config to disk: {e}")
            return
        try:
            yaml.dump(self._data, tf)
        except OSError as e:
            log.warning(f"Failed to write updated config to tempfile: {e}")
            tf.file.close()
            os.remove(tf.name)
            return
        tf.file.close()
        try:
            os.rename(tf.name, self.path)
        except OSError as e:
            log.warning(f"Failed to rename tempfile with updated config to {self.path}: {e}")
            try:
                os.remove(tf.name)
            except FileNotFoundError:
                pass
