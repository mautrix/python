# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any, Iterable, Type, Tuple, Optional, cast

from ..primitive import JSON
from .serializable import Serializable


def _is_descriptor(obj):
    return (hasattr(obj, '__get__') or
            hasattr(obj, '__set__') or
            hasattr(obj, '__delete__'))


class ExtensibleEnumMeta(type):
    _by_value: Dict[Any, 'ExtensibleEnum']
    _by_key: Dict[str, 'ExtensibleEnum']

    def __new__(mcs: Type['ExtensibleEnumMeta'], name: str, bases: Tuple[Type, ...],
                classdict: Dict[str, Any]) -> Type['ExtensibleEnum']:
        create = [(key, val) for key, val in classdict.items()
                  if not key.startswith("_") and not _is_descriptor(val)]
        classdict = {key: val for key, val in classdict.items()
                     if key.startswith("_") or _is_descriptor(val)}
        enum_class = cast(Type['ExtensibleEnum'], super().__new__(mcs, name, bases, classdict))
        for key, val in create:
            ExtensibleEnum.__new__(enum_class, val).key = key
        return enum_class

    def __bool__(cls: Type['ExtensibleEnum']) -> bool:
        return True

    def __contains__(cls: Type['ExtensibleEnum'], value: Any) -> bool:
        if isinstance(value, cls):
            return value in cls._by_value.values()
        else:
            return value in cls._by_value.keys()

    def __getattr__(cls: Type['ExtensibleEnum'], name: Any) -> 'ExtensibleEnum':
        try:
            return cls._by_key[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(cls: Type['ExtensibleEnum'], key: str, value: Any) -> None:
        if key.startswith("_"):
            return super().__setattr__(key, value)
        if not isinstance(value, cls):
            value = cls(value)
        value.key = key

    def __getitem__(cls: Type['ExtensibleEnum'], name: str) -> 'ExtensibleEnum':
        try:
            return cls._by_key[name]
        except KeyError:
            raise KeyError(name) from None

    def __setitem__(cls: Type['ExtensibleEnum'], key: str, value: Any) -> None:
        return cls.__setattr__(cls, key, value)

    def __iter__(cls: Type['ExtensibleEnum']) -> Iterable['ExtensibleEnum']:
        return cls._by_key.values().__iter__()

    def __len__(cls: Type['ExtensibleEnum']) -> int:
        return len(cls._by_key)

    def __repr__(cls: Type['ExtensibleEnum']) -> str:
        return f"<ExtensibleEnum {cls.__name__!r}>"


class ExtensibleEnum(Serializable, metaclass=ExtensibleEnumMeta):
    _by_value: Dict[Any, 'ExtensibleEnum'] = {}
    _by_key: Dict[str, 'ExtensibleEnum'] = {}

    _inited: bool = False
    _key: Optional[str]
    value: Any

    def __init__(self, value: Any) -> None:
        if self._inited:
            return
        self.value = value
        self._key = None
        self._inited = True

    def __new__(cls: Type['ExtensibleEnum'], value: Any) -> 'ExtensibleEnum':
        try:
            return cls._by_value[value]
        except KeyError as e:
            self = super().__new__(cls)
            self.__objclass__ = cls
            self.__init__(value)
            cls._by_value[value] = self
            return self

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        if self._key:
            return f"<{self.__class__.__name__}.{self._key}: {self.value!r}>"
        else:
            return f"{self.__class__.__name__}({self.value!r})"

    @property
    def key(self) -> str:
        return self._key

    @key.setter
    def key(self, key: str) -> None:
        self._key = key
        self._by_key[key] = self

    def serialize(self) -> JSON:
        return self.value

    @classmethod
    def deserialize(cls, raw: JSON) -> Any:
        return cls(raw)
