from typing import Generic, TypeVar, Any
from abc import ABC, abstractmethod
from enum import Enum
import json

from .....api import JSON

T = TypeVar("T")


class Serializable:
    """Serializable is the base class for types with custom JSON serializers."""

    def serialize(self) -> JSON:
        """Convert this object into JSON."""
        raise NotImplementedError()

    @classmethod
    def deserialize(cls, raw: JSON) -> Any:
        """Convert the given data parsed from JSON into an object of this type."""
        raise NotImplementedError()


class SerializerError(Exception):
    """
    SerializerErrors are raised if something goes wrong during serialization or deserialization.
    """
    pass


class GenericSerializable(ABC, Generic[T], Serializable):
    @classmethod
    @abstractmethod
    def deserialize(cls, raw: JSON) -> T:
        pass

    def json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def parse_json(cls, data: str) -> T:
        return cls.deserialize(json.loads(data))


SerializableEnumChild = TypeVar("SerializableEnumChild", bound='SerializableEnum')


class SerializableEnum(Serializable, Enum):
    # A fake __init__ to stop the type checker from complaining.
    def __init__(self, _):
        super().__init__()

    def serialize(self) -> str:
        return self.value

    @classmethod
    def deserialize(cls, raw: str) -> SerializableEnumChild:
        try:
            return cls(raw)
        except ValueError as e:
            raise SerializerError() from e

    def json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def parse_json(cls, data: str) -> SerializableEnumChild:
        return cls.deserialize(json.loads(data))

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value
