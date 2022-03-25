# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Callable
from abc import ABC

from ruamel.yaml.comments import CommentedMap

from .base import BaseConfig
from .recursive_dict import RecursiveDict


class BaseProxyConfig(BaseConfig, ABC):
    def __init__(
        self,
        load: Callable[[], CommentedMap],
        load_base: Callable[[], RecursiveDict[CommentedMap] | None],
        save: Callable[[RecursiveDict[CommentedMap]], None],
    ) -> None:
        super().__init__()
        self._data = CommentedMap()
        self._load_proxy = load
        self._load_base_proxy = load_base
        self._save_proxy = save

    def load(self) -> None:
        self._data = self._load_proxy() or CommentedMap()

    def load_base(self) -> RecursiveDict[CommentedMap] | None:
        return self._load_base_proxy()

    def save(self) -> None:
        self._save_proxy(self._data)
