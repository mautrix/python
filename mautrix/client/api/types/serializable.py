from typing import Generic, List, Set, Dict, Type, TypeVar, Any, Union, Optional, Tuple, Iterator
from abc import ABC, abstractmethod
from enum import Enum
import attr
import json

from ....types import JSON
from .obj import Obj, Lst

T = TypeVar("T")
T2 = TypeVar("T2")


class Serializable:
    @abstractmethod
    def serialize(self) -> JSON:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def deserialize(cls, raw: JSON) -> Any:
        raise NotImplementedError()


class GenericSerializable(ABC, Generic[T], Serializable):
    @classmethod
    @abstractmethod
    def deserialize(cls, raw: JSON) -> T:
        raise NotImplementedError()

    def json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def parse_json(cls, data: str) -> T:
        return cls.deserialize(json.loads(data))


SerializableEnumChild = TypeVar("SerializableEnumChild", bound='SerializableEnum')


class SerializableEnum(Serializable, Enum):
    def serialize(self) -> JSON:
        return self.value

    @classmethod
    def deserialize(cls, raw: JSON) -> SerializableEnumChild:
        return cls(raw)

    def json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def parse_json(cls, data: str) -> SerializableEnumChild:
        return cls.deserialize(json.loads(data))


def _fields(attrs_type: Type[T]) -> Iterator[Tuple[str, Type[T2]]]:
    return ((field.metadata.get("json", field.name), field) for field in attr.fields(attrs_type))


def _dict_to_attrs(attrs_type: Type[T], data: JSON, default: Optional[T] = None,
                   default_if_empty: bool = False) -> T:
    data = data or {}
    # Initialize with unflattened data
    new_items = {field.name: _deserialize(field.type, data, field.default)
                 for _, field in _fields(attrs_type)
                 if field.metadata.get("flatten", False)}
    # Loop through items to add rest of data
    fields = dict(_fields(attrs_type))
    for key, value in data.items():
        try:
            field = fields[key]
        except KeyError:
            continue
        if field.metadata.get("flatten", False):
            continue
        new_items[field.name] = _deserialize(field.type, value, field.default)
    if len(new_items) == 0 and default_if_empty:
        return default
    return attrs_type(**new_items)


def _deserialize(cls: Type[T], value: JSON, default: Optional[T] = None) -> T:
    if value is None:
        return default

    cls = getattr(cls, "__supertype__", None) or cls
    if attr.has(cls):
        return _dict_to_attrs(cls, value, default, default_if_empty=True)
    elif cls == Any or cls == JSON:
        return value
    elif issubclass(cls, List):
        item_cls, = getattr(cls, "__args__", default=(None,))
        return [_deserialize(item_cls, item) for item in value]
    elif issubclass(cls, Set):
        item_cls, = getattr(cls, "__args__", default=(None,))
        return {_deserialize(item_cls, item) for item in value}
    elif issubclass(cls, Dict):
        key_cls, val_cls = getattr(cls, "__args__", default=(None, None))
        return {key: _deserialize(val_cls, item) for key, item in value}
    elif type(cls) == type(Union) and len(cls.__args__) == 2 and isinstance(None, cls.__args__[1]):
        return _deserialize(cls.__args__[0], value)
    elif issubclass(cls, Serializable):
        return cls.deserialize(value)
    elif isinstance(value, list):
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
        serialized = _serialize(field_val)
        if field.metadata.get("flatten", False) and isinstance(serialized, dict):
            new_dict.update(serialized)
        else:
            new_dict[json_name] = serialized
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
    @classmethod
    def deserialize(cls, data: JSON) -> T:
        return _dict_to_attrs(cls, data)

    def serialize(self) -> JSON:
        return _attrs_to_dict(self)
