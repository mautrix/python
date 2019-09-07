# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Any, List, Iterable, Type

from mautrix.api import JSON
from .serializable import Serializable


class ExtensibleEnumMeta(type):
    _by_value: Dict[Any, 'ExtensibleEnum']
    _by_key: Dict[str, 'ExtensibleEnum']

    @classmethod
    def __prepare__(metacls: Type['ExtensibleEnumMeta'], cls: Type['ExtensibleEnum'],
                    bases: List[Type]) -> Dict[str, Any]:
        if ExtensibleEnum not in bases or cls == ExtensibleEnum:
            return {}
        data = {}
        print(metacls)
        print(cls)
        print(dir(cls))
        print(bases)
        return data

    def __bool__(cls: Type['ExtensibleEnum']) -> bool:
        return True

    def __contains__(cls: Type['ExtensibleEnum'], value: Any) -> bool:
        return value in cls._by_value

    def __getattr__(cls: Type['ExtensibleEnum'], value: Any) -> 'ExtensibleEnum':
        return cls._by_value[value]

    def __setattr__(cls: Type['ExtensibleEnum'], key: str, value: Any) -> None:
        if isinstance(value, cls):
            cls._by_key[key] = value
        else:
            cls._by_key[key] = cls(value)

    def __getitem__(cls: Type['ExtensibleEnum'], key: str) -> 'ExtensibleEnum':
        return cls._by_key[key]

    def __iter__(cls: Type['ExtensibleEnum']) -> Iterable['ExtensibleEnum']:
        return cls._by_key.values().__iter__()

    def __len__(cls: Type['ExtensibleEnum']) -> int:
        return len(cls._by_key)

    def __repr__(cls: Type['ExtensibleEnum']) -> str:
        return f"<ExtensibleEnum {cls.__name__}>"


class ExtensibleEnum(Serializable, metaclass=ExtensibleEnumMeta):
    _by_value: Dict[Any, 'ExtensibleEnum'] = {}
    _by_key: Dict[str, 'ExtensibleEnum'] = {}
    value: Any

    def __init__(self, value: Any) -> None:
        self.value = value

    def __new__(cls, value: Any, *args, **kwargs) -> 'ExtensibleEnum':
        try:
            return cls._by_value[value]
        except KeyError:
            self = super().__new__(cls, value, *args, **kwargs)
            cls._by_value[value] = self
            return self

    def serialize(self) -> JSON:
        return self.value

    @classmethod
    def deserialize(cls, raw: JSON) -> Any:
        return cls(raw)
