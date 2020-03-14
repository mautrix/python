# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Optional, Tuple, Generic, TypeVar, Type
import copy

from ruamel.yaml.comments import CommentedMap

T = TypeVar('T')


class RecursiveDict(Generic[T]):
    def __init__(self, data: Optional[T] = None, dict_factory: Optional[Type[T]] = None) -> None:
        self._dict_factory = dict_factory or dict
        self._data: CommentedMap = data or self._dict_factory()

    def clone(self) -> 'RecursiveDict':
        return RecursiveDict(data=copy.deepcopy(self._data), dict_factory=self._dict_factory)

    @staticmethod
    def parse_key(key: str) -> Tuple[str, Optional[str]]:
        if '.' not in key:
            return key, None
        key, next_key = key.split('.', 1)
        if len(key) > 0 and key[0] == "[":
            end_index = next_key.index("]")
            key = key[1:] + "." + next_key[:end_index]
            next_key = next_key[end_index + 2:] if len(next_key) > end_index + 1 else None
        return key, next_key

    def _recursive_get(self, data: T, key: str, default_value: Any) -> Any:
        key, next_key = self.parse_key(key)
        if next_key is not None:
            next_data = data.get(key, self._dict_factory())
            return self._recursive_get(next_data, next_key, default_value)
        try:
            return data[key]
        except (AttributeError, KeyError):
            return default_value

    def get(self, key: str, default_value: Any, allow_recursion: bool = True) -> Any:
        if allow_recursion and '.' in key:
            return self._recursive_get(self._data, key, default_value)
        return self._data.get(key, default_value)

    def __getitem__(self, key: str) -> Any:
        return self.get(key, None)

    def __contains__(self, key: str) -> bool:
        return self.get(key, None) is not None

    def _recursive_set(self, data: T, key: str, value: Any) -> None:
        key, next_key = self.parse_key(key)
        if next_key is not None:
            if key not in data:
                data[key] = self._dict_factory()
            next_data = data.get(key, self._dict_factory())
            return self._recursive_set(next_data, next_key, value)
        data[key] = value

    def set(self, key: str, value: Any, allow_recursion: bool = True) -> None:
        if allow_recursion and '.' in key:
            self._recursive_set(self._data, key, value)
            return
        self._data[key] = value

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def _recursive_del(self, data: T, key: str) -> None:
        key, next_key = self.parse_key(key)
        if next_key is not None:
            if key not in data:
                return
            next_data = data[key]
            return self._recursive_del(next_data, next_key)
        try:
            del data[key]
            del data.ca.items[key]
        except KeyError:
            pass

    def delete(self, key: str, allow_recursion: bool = True) -> None:
        if allow_recursion and '.' in key:
            self._recursive_del(self._data, key)
            return
        try:
            del self._data[key]
            del self._data.ca.items[key]
        except KeyError:
            pass

    def __delitem__(self, key: str) -> None:
        self.delete(key)
