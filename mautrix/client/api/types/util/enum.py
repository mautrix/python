# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any, List, Iterable, Type, Tuple

from mautrix.api import JSON
from .serializable import Serializable


def _is_descriptor(obj):
    return (
            hasattr(obj, '__get__') or
            hasattr(obj, '__set__') or
            hasattr(obj, '__delete__'))


class ExtensibleEnumMeta(type):
    _by_value: Dict[Any, 'ExtensibleEnum']
    _by_key: Dict[str, 'ExtensibleEnum']

    def __new__(mcs: Type['ExtensibleEnumMeta'], name: str, bases: Tuple[Type, ...],
                classdict: Dict[str, Any]) -> Dict[str, any]:
        print(f"__new__({mcs=}, {name=}, {bases=}, {classdict=})")
        enum_class = super().__new__(mcs, name, bases, classdict)
        enum_class._by_value = {}
        enum_class._by_key = {}
        for key, val in classdict.items():
            if key.startswith("_") or _is_descriptor(val):
                continue
            enum_member = __new__(enum_class)
            enum_member.__objclass__ = enum_class
            enum_member.__init__(val)
            enum_class._by_key[key] = enum_member
            enum_class._by_value[val] = enum_member
        return enum_class

    def __bool__(cls: Type['ExtensibleEnum']) -> bool:
        return True

    def __contains__(cls: Type['ExtensibleEnum'], value: Any) -> bool:
        print(f"__contains__({cls=}, {value=})")
        if isinstance(value, cls):
            return value in cls._by_value.values()
        else:
            return value in cls._by_value.keys()

    def __getattr__(cls: Type['ExtensibleEnum'], name: Any) -> 'ExtensibleEnum':
        print(f"__getattr__({cls=}, {name=})")
        try:
            return cls._by_key[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(cls: Type['ExtensibleEnum'], key: str, value: Any) -> None:
        print(f"__setattr__({cls=}, {key=}, {value=})")
        if key.startswith("_"):
            return super().__setattr__(key, value)
        if not isinstance(value, cls):
            value = cls(value)
        cls._by_key[key] = value
        cls._by_value[value.value] = value
        return super().__setattr__(key, value)

    def __getitem__(cls: Type['ExtensibleEnum'], name: str) -> 'ExtensibleEnum':
        print(f"__getitem__({cls=}, {name=})")
        try:
            return cls._by_key[name]
        except KeyError:
            raise KeyError(name) from None

    def __setitem__(cls: Type['ExtensibleEnum'], key: str, value: Any) -> None:
        return cls.__setattr__(cls, key, value)

    def __iter__(cls: Type['ExtensibleEnum']) -> Iterable['ExtensibleEnum']:
        print(f"__iter__({cls=})")
        return cls._by_key.values().__iter__()

    def __len__(cls: Type['ExtensibleEnum']) -> int:
        print(f"__len__({cls=})")
        return len(cls._by_key)

    def __repr__(cls: Type['ExtensibleEnum']) -> str:
        return f"<ExtensibleEnum {cls.__name__!r}>"


class ExtensibleEnum(Serializable, metaclass=ExtensibleEnumMeta):
    _by_value: Dict[Any, 'ExtensibleEnum'] = {}
    _by_key: Dict[str, 'ExtensibleEnum'] = {}
    value: Any

    def __init__(self, value: Any) -> None:
        print(f"__init__({self=}, {value=})")
        self.value = value

    def __new__(cls, value: Any, *args, **kwargs) -> 'ExtensibleEnum':
        print(f"__new__({cls=}, {value=}, {args=}, {kwargs=})")
        try:
            return cls._by_value[value]
        except KeyError:
            self = super().__new__(cls, value, *args, **kwargs)
            cls._by_value[value] = self
            return self

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return repr(self.value)

    def serialize(self) -> JSON:
        return self.value

    @classmethod
    def deserialize(cls, raw: JSON) -> Any:
        return cls(raw)
