from typing import (List, Set, Dict, Type, TypeVar, Any, Union, Optional, Tuple, Iterator, Callable,
                    NewType)
import attr
import copy

from .....api import JSON
from .serializable import SerializerError, Serializable, GenericSerializable
from .obj import Obj, Lst

T = TypeVar("T")
T2 = TypeVar("T2")

Serializer = NewType("Serializer", Callable[[T], JSON])
Deserializer = NewType("Deserializer", Callable[[JSON], T])
serializer_map: Dict[Type[T], Serializer] = {}
deserializer_map: Dict[Type[T], Deserializer] = {}


def serializer(elem_type: Type[T]) -> Callable[[Serializer], Serializer]:
    def decorator(func: Serializer) -> Serializer:
        serializer_map[elem_type] = func
        return func

    return decorator


def deserializer(elem_type: Type[T]) -> Callable[[Deserializer], Deserializer]:
    def decorator(func: Deserializer) -> Deserializer:
        deserializer_map[elem_type] = func
        return func

    return decorator


def _fields(attrs_type: Type[T], only_if_flatten: bool = None) -> Iterator[Tuple[str, Type[T2]]]:
    return ((field.metadata.get("json", field.name), field) for field in attr.fields(attrs_type)
            if only_if_flatten is None or field.metadata.get("flatten", False) == only_if_flatten)


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
    if len(new_items) == 0 and default_if_empty:
        return _safe_default(default)
    try:
        obj = attrs_type(**new_items)
    except TypeError as e:
        for json_key, field in _fields(attrs_type):
            if not field.default and json_key not in new_items:
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


def _deserialize(cls: Type[T], value: JSON, default: Optional[T] = None) -> T:
    if value is None:
        return _safe_default(default)

    cls = getattr(cls, "__supertype__", None) or cls
    try:
        return deserializer_map[cls](value)
    except KeyError:
        pass
    if attr.has(cls):
        return _dict_to_attrs(cls, value, default, default_if_empty=True)
    elif cls == Any or cls == JSON:
        return value
    elif type(cls) == type(Union):
        if len(cls.__args__) == 2 and isinstance(None, cls.__args__[1]):
            return _deserialize(cls.__args__[0], value, default)
    elif issubclass(cls, Serializable):
        return cls.deserialize(value)
    elif issubclass(cls, List):
        item_cls, = getattr(cls, "__args__", (None,))
        return [_deserialize(item_cls, item) for item in value]
    elif issubclass(cls, Set):
        item_cls, = getattr(cls, "__args__", (None,))
        return {_deserialize(item_cls, item) for item in value}
    elif issubclass(cls, Dict):
        key_cls, val_cls = getattr(cls, "__args__", (None, None))
        return {key: _deserialize(val_cls, item) for key, item in value.items()}
    if isinstance(value, list):
        return Lst(value)
    elif isinstance(value, dict):
        return Obj(**value)
    return value


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
            serialized = serializer_map[field.type](field_val)
        except KeyError:
            serialized = _serialize(field_val)
        if field.metadata.get("flatten", False) and isinstance(serialized, dict):
            new_dict.update(serialized)
        else:
            new_dict[json_name] = serialized
    try:
        new_dict.update(data.unrecognized_)
    except (AttributeError, TypeError):
        pass
    return new_dict


def _serialize(val: Any) -> JSON:
    if attr.has(val.__class__):
        return _attrs_to_dict(val)
    elif isinstance(val, (tuple, list, set)):
        return [_serialize(subval) for subval in val]
    elif isinstance(val, dict):
        return {_serialize(subkey): _serialize(subval) for subkey, subval in val.items()}
    elif isinstance(val, Serializable):
        return val.serialize()
    return val


class SerializableAttrs(GenericSerializable[T]):
    """An abstract :class:`Serializable` that assumes the subclass"""
    unrecognized_: Optional[JSON] = None

    @classmethod
    def deserialize(cls, data: JSON) -> T:
        return _dict_to_attrs(cls, data)

    def serialize(self) -> JSON:
        return _attrs_to_dict(self)

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            return self.unrecognized_[item]
