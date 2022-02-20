# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from abc import ABC, abstractmethod

from ruamel.yaml.comments import Comment, CommentedBase, CommentedMap

from .recursive_dict import RecursiveDict


class BaseMissingError(ValueError):
    pass


class ConfigUpdateHelper:
    base: RecursiveDict[CommentedMap]

    def __init__(self, base: RecursiveDict, config: RecursiveDict) -> None:
        self.base = base
        self.source = config

    def copy(self, from_path: str, to_path: str | None = None) -> None:
        if from_path in self.source:
            val = self.source[from_path]
            # Small hack to make sure comments from the user config don't
            # partially leak into the updated version.
            if isinstance(val, CommentedBase):
                setattr(val, Comment.attrib, Comment())
            self.base[to_path or from_path] = val

    def copy_dict(
        self,
        from_path: str,
        to_path: str | None = None,
        override_existing_map: bool = True,
    ) -> None:
        if from_path in self.source:
            to_path = to_path or from_path
            if override_existing_map or to_path not in self.base:
                self.base[to_path] = CommentedMap()
            for key, value in self.source[from_path].items():
                self.base[to_path][key] = value

    def __iter__(self):
        yield self.copy
        yield self.copy_dict
        yield self.base


class BaseConfig(ABC, RecursiveDict[CommentedMap]):
    @abstractmethod
    def load(self) -> None:
        pass

    @abstractmethod
    def load_base(self) -> RecursiveDict[CommentedMap] | None:
        pass

    def load_and_update(self) -> None:
        self.load()
        self.update()

    @abstractmethod
    def save(self) -> None:
        pass

    def update(self, save: bool = True) -> None:
        base = self.load_base()
        if not base:
            raise BaseMissingError("Can't update() without base config")

        self.do_update(ConfigUpdateHelper(base, self))
        self._data = base._data
        if save:
            self.save()

    @abstractmethod
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        pass
