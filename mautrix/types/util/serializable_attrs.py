# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Type, TypeVar, Any, Union, Optional, Tuple, Iterator, Callable, NewType
from uuid import UUID
import attr
import copy
import sys

from ..primitive import JSON
from .serializable import SerializerError, Serializable, GenericSerializable
from .obj import Obj, Lst

T = TypeVar("T")
T2 = TypeVar("T2")

Serializer = NewType("Serializer", Callable[[T], JSON])
Deserializer = NewType("Deserializer", Callable[[JSON], T])
serializer_map: Dict[Type[T], Serializer] = {
    UUID: str,
}
deserializer_map: Dict[Type[T], Deserializer] = {
    UUID: UUID,
}

no_value = object()


def serializer(elem_type: Type[T]) -> Callable[[Serializer], Serializer]:
    """
    Define a custom serialization function for the given type.

    Args:
        elem_type: The type to define the serializer for.

    Returns:
        Decorator for the function.

    Examples:
        >>> from datetime import datetime
        >>> from mautrix.types import serializer, JSON
        >>> @serializer(datetime)
        ... def serialize_datetime(dt: datetime) -> JSON:
        ...     return dt.timestamp()
    """

    def decorator(func: Serializer) -> Serializer:
        serializer_map[elem_type] = func
        return func

    return decorator


def deserializer(elem_type: Type[T]) -> Callable[[Deserializer], Deserializer]:
    """
    Define a custom deserialization function for a given type hint.

    Args:
        elem_type: The type hint to define the deserializer for.

    Returns:
        Decorator for the function:

    Examples:
        >>> from datetime import datetime
        >>> from mautrix.types import deserializer, JSON
        >>> @deserializer(datetime)
        ... def deserialize_datetime(data: JSON) -> datetime:
        ...     return datetime.fromtimestamp(data)
    """

    def decorator(func: Deserializer) -> Deserializer:
        deserializer_map[elem_type] = func
        return func

    return decorator


def _fields(attrs_type: Type[T], only_if_flatten: bool = None) -> Iterator[Tuple[str, Type[T2]]]:
    return ((field.metadata.get("json", field.name), field) for field in attr.fields(attrs_type)
            if only_if_flatten is None or field.metadata.get("flatten", False) == only_if_flatten
            and not field.metadata.get("hidden", False))


immutable = (int, str, float, bool, type(None))


def _safe_default(val: T) -> T:
    if isinstance(val, immutable):
        return val
    return copy.copy(val)


def _dict_to_attrs(attrs_type: Type[T], data: JSON, default: Optional[T] = None,
                   default_if_empty: bool = False) -> T:
    data = data or {}
    unrecognized = {}
    new_items = {field.name.lstrip("_"):
                     _try_deserialize(field.type, data, field.default,
                                      field.metadata.get("ignore_errors", False))
                 for _, field in _fields(attrs_type, only_if_flatten=True)}
    fields = dict(_fields(attrs_type, only_if_flatten=False))
    for key, value in data.items():
        try:
            field = fields[key]
        except KeyError:
            unrecognized[key] = value
            continue
        name = field.name.lstrip("_")
        new_items[name] = _try_deserialize(field.type, value, field.default,
                                           field.metadata.get("ignore_errors", False))
    if len(new_items) == 0 and default_if_empty and default is not attr.NOTHING:
        return _safe_default(default)
    try:
        obj = attrs_type(**new_items)
    except TypeError as e:
        for key, field in _fields(attrs_type):
            json_key = field.metadata.get("json", key)
            if field.default is attr.NOTHING and json_key not in new_items:
                raise SerializerError(
                    f"Missing value for required key {field.name} in {attrs_type.__name__}") from e
        raise SerializerError("Unknown serialization error") from e
    if len(unrecognized) > 0:
        obj.unrecognized_ = unrecognized
    return obj


def _try_deserialize(cls: Type[T], value: JSON, default: Optional[T] = None,
                     ignore_errors: bool = False) -> T:
    try:
        return _deserialize(cls, value, default)
    except SerializerError:
        if not ignore_errors:
            raise
    except (TypeError, ValueError, KeyError) as e:
        if not ignore_errors:
            raise SerializerError("Unknown serialization error") from e


def _has_custom_deserializer(cls) -> bool:
    return (issubclass(cls, Serializable) and
            getattr(cls.deserialize, '__func__')
            != getattr(SerializableAttrs.deserialize, '__func__'))


def _deserialize(cls: Type[T], value: JSON, default: Optional[T] = None) -> T:
    if value is None:
        return _safe_default(default)

    try:
        deser = deserializer_map[cls]
    except KeyError:
        pass
    else:
        return deser(value)
    supertype = getattr(cls, "__supertype__", None)
    if supertype:
        cls = supertype
        try:
            deser = deserializer_map[supertype]
        except KeyError:
            pass
        else:
            return deser(value)
    if attr.has(cls):
        if _has_custom_deserializer(cls):
            return cls.deserialize(value)
        return _dict_to_attrs(cls, value, default, default_if_empty=True)
    elif cls == Any or cls == JSON:
        return value
    elif getattr(cls, "__origin__", None) is Union:
        if len(cls.__args__) == 2 and isinstance(None, cls.__args__[1]):
            return _deserialize(cls.__args__[0], value, default)
    elif isinstance(cls, type):
        if issubclass(cls, Serializable):
            return cls.deserialize(value)

    type_class = _get_type_class(cls)
    args = getattr(cls, "__args__", None)
    if type_class == list:
        item_cls, = args
        return [_deserialize(item_cls, item) for item in value]
    elif type_class == set:
        item_cls, = args
        return {_deserialize(item_cls, item) for item in value}
    elif type_class == dict:
        key_cls, val_cls = args
        return {_deserialize(key_cls, key): _deserialize(val_cls, item)
                for key, item in value.items()}

    if isinstance(value, list):
        return Lst(value)
    elif isinstance(value, dict):
        return Obj(**value)
    return value


if sys.version_info >= (3, 7):
    def _get_type_class(typ):
        try:
            return typ.__origin__
        except AttributeError:
            return None
else:
    def _get_type_class(typ):
        try:
            return typ.__extra__
        except AttributeError:
            return None


def _actual_type(cls: Type[T]) -> Type[T]:
    if cls is None:
        return cls
    if getattr(cls, "__origin__", None) is Union:
        if len(cls.__args__) == 2 and isinstance(None, cls.__args__[1]):
            return cls.__args__[0]
    return cls


def _attrs_to_dict(data: T) -> JSON:
    new_dict = {}
    for json_name, field in _fields(data.__class__):
        if not json_name:
            continue
        field_val = getattr(data, field.name)
        if field_val is None:
            if not field.metadata.get("omitempty", True):
                field_val = field.default
            else:
                continue
        if field.metadata.get("omitdefault", False) and field_val == field.default:
            continue
        try:
            serialized = serializer_map[_actual_type(field.type)](field_val)
        except KeyError:
            serialized = _serialize(field_val)
        if field.metadata.get("flatten", False) and isinstance(serialized, dict):
            new_dict.update(serialized)
        elif serialized != no_value:
            new_dict[json_name] = serialized
    try:
        new_dict.update(data.unrecognized_)
    except (AttributeError, TypeError):
        pass
    return new_dict


def _serialize(val: Any) -> JSON:
    if isinstance(val, Serializable):
        return val.serialize()
    elif isinstance(val, (tuple, list, set)):
        return [_serialize(subval) for subval in val]
    elif isinstance(val, dict):
        return {_serialize(subkey): _serialize(subval) for subkey, subval in val.items()}
    elif attr.has(val.__class__):
        return _attrs_to_dict(val)
    return val


class SerializableAttrs(GenericSerializable[T]):
    """
    An abstract :class:`Serializable` that assumes the subclass is an attrs dataclass.

    Examples:
        >>> from attr import dataclass
        >>> from mautrix.types import SerializableAttrs
        >>> @dataclass
        ... class Foo(SerializableAttrs['Foo']):
        ...     index: int
        ...     field: Optional[str] = None
    """
    unrecognized_: Optional[JSON]

    def __init__(self):
        self.unrecognized_ = {}

    @classmethod
    def deserialize(cls, data: JSON) -> T:
        return _dict_to_attrs(cls, data)

    def serialize(self) -> JSON:
        return _attrs_to_dict(self)

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            try:
                return self.unrecognized_[item]
            except AttributeError:
                self.unrecognized_ = {}
                raise KeyError(item)

    def __setitem__(self, item, value):
        if hasattr(self, item):
            setattr(self, item, value)
        else:
            try:
                self.unrecognized_[item] = value
            except AttributeError:
                self.unrecognized_ = {
                    item: value,
                }
