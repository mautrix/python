# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from abc import ABC
import io

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .base import BaseConfig
from .recursive_dict import RecursiveDict

yaml = YAML()
yaml.indent(4)
yaml.width = 200


class BaseStringConfig(BaseConfig, ABC):
    def __init__(self, data: str, base_data: str) -> None:
        super().__init__()
        self._data = yaml.load(data)
        self._base = RecursiveDict(yaml.load(base_data), CommentedMap)

    def load(self) -> None:
        pass

    def load_base(self) -> RecursiveDict[CommentedMap] | None:
        return self._base

    def save(self) -> str:
        buf = io.StringIO()
        yaml.dump(self._data, buf)
        return buf.getvalue()
