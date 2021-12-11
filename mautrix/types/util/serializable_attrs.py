# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Callable, Dict, Iterator, NewType, Optional, Tuple, Type, TypeVar, Union
from uuid import UUID
import copy
import logging

import attr

from ..primitive import JSON
from .obj import Lst, Obj
from .serializable import (
    AbstractSerializable,
    Serializable,
    SerializableSubtype,
    SerializerError,
    UnknownSerializationError,
)

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

META_JSON = "json"
META_FLATTEN = "flatten"
META_HIDDEN = "hidden"
META_IGNORE_ERRORS = "ignore_errors"
META_OMIT_EMPTY = "omitempty"
META_OMIT_DEFAULT = "omitdefault"

log = logging.getLogger("mau.attrs")


def field(
    default: Any = attr.NOTHING,
    factory: Optional[Callable[[], Any]] = None,
    json: Optional[str] = None,
    flatten: bool = False,
    hidden: bool = False,
    ignore_errors: bool = False,
    omit_empty: bool = True,
    omit_default: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
):
    """
    A wrapper around :meth:`attr.ib` to conveniently add SerializableAttrs metadata fields.

    Args:
        default: Same as attr.ib, the default value for the field.
        factory: Same as attr.ib, a factory function that creates the default value.
        json: The JSON key used for de/serializing the object.
        flatten: Set to flatten subfields inside this field to be a part of the parent object in
            serialized objects. When deserializing, the input data will be deserialized into both
            the parent and child fields, so the classes should ignore unknown keys.
        hidden: Set to always omit the key from serialized objects.
        ignore_errors: Set to ignore type errors while deserializing.
        omit_empty: Set to omit the key from serialized objects if the value is ``None``.
        omit_default: Set to omit the key from serialized objects if the value is equal to the
            default.
        metadata: Additional metadata for attr.ib.
        **kwargs: Additional keyword arguments for attr.ib.

    Returns:
        The decorator function returned by attr.ib.

    Examples:
        >>> from attr import dataclass
        >>> from mautrix.types import SerializableAttrs, field
        >>> @dataclass
        ... class SomeData(SerializableAttrs):
        ...     my_field: str = field(json="com.example.namespaced_field", default="hi")
        ...
        >>> SomeData().serialize()
        {'com.example.namespaced_field': 'hi'}
        >>> SomeData.deserialize({"com.example.namespaced_field": "hmm"})
        SomeData(my_field='hmm')
    """
    custom_meta = {
        META_JSON: json,
        META_FLATTEN: flatten,
        META_HIDDEN: hidden,
        META_IGNORE_ERRORS: ignore_errors,
        META_OMIT_EMPTY: omit_empty,
        META_OMIT_DEFAULT: omit_default,
    }
    metadata = metadata or {}
    metadata.update({k: v for k, v in custom_meta.items() if v is not None})
    return attr.ib(default=default, factory=factory, metadata=metadata, **kwargs)


def serializer(elem_type: Type[T]) -> Callable[[Serializer], Serializer]:
    """
    Define a custom serialization function for the given type.

    Args:
        elem_type: The type to define the serializer for.

    Returns:
        Decorator for the function. The decorator will simply add the function to a map of
        deserializers and return the function.

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
        Decorator for the function. The decorator will simply add the function to a map of
        deserializers and return the function.

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
    for field in attr.fields(attrs_type):
        if field.metadata.get(META_HIDDEN, False):
            continue
        if only_if_flatten is None or field.metadata.get(META_FLATTEN, False) == only_if_flatten:
            yield field.metadata.get(META_JSON, field.name), field


immutable = int, str, float, bool, type(None)


def _safe_default(val: T) -> T:
    if isinstance(val, immutable):
        return val
    elif val is attr.NOTHING:
        return None
    elif isinstance(val, attr.Factory):
        if val.takes_self:
            # TODO implement?
            return None
        else:
            return val.factory()
    return copy.copy(val)


def _dict_to_attrs(
    attrs_type: Type[T], data: JSON, default: Optional[T] = None, default_if_empty: bool = False
) -> T:
    data = data or {}
    unrecognized = {}
    new_items = {
        field_meta.name.lstrip("_"): _try_deserialize(field_meta, data)
        for _, field_meta in _fields(attrs_type, only_if_flatten=True)
    }
    fields = dict(_fields(attrs_type, only_if_flatten=False))
    for key, value in data.items():
        try:
            field_meta = fields[key]
        except KeyError:
            unrecognized[key] = value
            continue
        name = field_meta.name.lstrip("_")
        try:
            new_items[name] = _try_deserialize(field_meta, value)
        except UnknownSerializationError as e:
            raise SerializerError(
                f"Failed to deserialize {value} into key {name} of {attrs_type.__name__}"
            ) from e
        except SerializerError:
            raise
        except Exception as e:
            raise SerializerError(
                f"Failed to deserialize {value} into key {name} of {attrs_type.__name__}"
            ) from e
    if len(new_items) == 0 and default_if_empty and default is not attr.NOTHING:
        return _safe_default(default)
    try:
        obj = attrs_type(**new_items)
    except TypeError as e:
        for key, field_meta in _fields(attrs_type):
            if field_meta.default is attr.NOTHING and key not in new_items:
                log.debug("Failed to deserialize %s into %s", data, attrs_type.__name__)
                json_key = field_meta.metadata.get(META_JSON, key)
                raise SerializerError(
                    f"Missing value for required key {json_key} in {attrs_type.__name__}"
                ) from e
        raise UnknownSerializationError() from e
    if len(unrecognized) > 0:
        obj.unrecognized_ = unrecognized
    return obj


def _try_deserialize(field, value: JSON) -> T:
    try:
        return _deserialize(field.type, value, field.default)
    except SerializerError:
        if not field.metadata.get(META_IGNORE_ERRORS, False):
            raise
    except (TypeError, ValueError, KeyError) as e:
        if not field.metadata.get(META_IGNORE_ERRORS, False):
            raise UnknownSerializationError() from e


def _has_custom_deserializer(cls) -> bool:
    return issubclass(cls, Serializable) and getattr(cls.deserialize, "__func__") != getattr(
        SerializableAttrs.deserialize, "__func__"
    )


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
    elif isinstance(cls, type) and issubclass(cls, Serializable):
        return cls.deserialize(value)

    type_class = getattr(cls, "__origin__", None)
    args = getattr(cls, "__args__", None)
    if type_class is Union:
        if len(args) == 2 and isinstance(None, args[1]):
            return _deserialize(args[0], value, default)
    elif type_class == list:
        (item_cls,) = args
        return [_deserialize(item_cls, item) for item in value]
    elif type_class == set:
        (item_cls,) = args
        return {_deserialize(item_cls, item) for item in value}
    elif type_class == dict:
        key_cls, val_cls = args
        return {
            _deserialize(key_cls, key): _deserialize(val_cls, item) for key, item in value.items()
        }

    if isinstance(value, list):
        return Lst(value)
    elif isinstance(value, dict):
        return Obj(**value)
    return value


def _actual_type(cls: Type[T]) -> Type[T]:
    if cls is None:
        return cls
    if getattr(cls, "__origin__", None) is Union:
        if len(cls.__args__) == 2 and isinstance(None, cls.__args__[1]):
            return cls.__args__[0]
    return cls


def _get_serializer(cls: Type[T]) -> Serializer:
    return serializer_map.get(_actual_type(cls), _serialize)


def _serialize_attrs_field(data: T, field: T2) -> JSON:
    field_val = getattr(data, field.name)
    if field_val is None:
        if not field.metadata.get(META_OMIT_EMPTY, True):
            if field.default is not attr.NOTHING:
                field_val = _safe_default(field.default)
        else:
            return attr.NOTHING

    if field.metadata.get(META_OMIT_DEFAULT, False) and field_val == field.default:
        return attr.NOTHING

    return _get_serializer(field.type)(field_val)


def _attrs_to_dict(data: T) -> JSON:
    new_dict = {}
    for json_name, field in _fields(data.__class__):
        if not json_name:
            continue
        serialized = _serialize_attrs_field(data, field)
        if serialized is not attr.NOTHING:
            if field.metadata.get(META_FLATTEN, False) and isinstance(serialized, dict):
                new_dict.update(serialized)
            else:
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


class SerializableAttrs(AbstractSerializable):
    """
    An abstract :class:`Serializable` that assumes the subclass is an attrs dataclass.

    Examples:
        >>> from attr import dataclass
        >>> from mautrix.types import SerializableAttrs
        >>> @dataclass
        ... class Foo(SerializableAttrs):
        ...     index: int
        ...     field: Optional[str] = None
    """

    unrecognized_: Dict[str, JSON]

    def __init__(self):
        self.unrecognized_ = {}

    @classmethod
    def deserialize(cls: Type[SerializableSubtype], data: JSON) -> SerializableSubtype:
        return _dict_to_attrs(cls, data)

    def serialize(self) -> JSON:
        return _attrs_to_dict(self)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in getattr(self, "unrecognized_", {})

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError:
            try:
                return self.unrecognized_[item]
            except AttributeError:
                self.unrecognized_ = {}
                raise KeyError(item)

    def __setitem__(self, item: str, value: Any) -> None:
        if hasattr(self, item):
            setattr(self, item, value)
        else:
            try:
                self.unrecognized_[item] = value
            except AttributeError:
                self.unrecognized_ = {item: value}
