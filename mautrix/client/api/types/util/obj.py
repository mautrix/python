# From https://github.com/Lonami/dumbot/blob/master/dumbot.py
# Modified to add Serializable base
from typing import Dict, List

from .....api import JSON
from .serializable import GenericSerializable, Serializable


class Obj(GenericSerializable['Obj']):
    def __init__(self, **kwargs):
        self.__dict__ = {k: Obj(**v) if isinstance(v, dict) else (
            Lst(v) if isinstance(v, list) else v) for k, v in kwargs.items()}

    def __getattr__(self, name):
        # FIXME: Why is this function needed? Is it just to strip the '_' from the name?
        name = name.rstrip('_')
        obj = self.__dict__.get(name)
        if obj is None:
            raise AttributeError(f"{self.__class__.__name__} object has no attribute {name}")
        else:
            return obj

    def __getitem__(self, name):
        return self.__dict__.get(name)

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __str__(self):
        return str(self.serialize())

    def __repr__(self):
        return repr(self.serialize())

    def __bool__(self):
        return bool(self.__dict__)

    def __contains__(self, item):
        return item in self.__dict__

    def popitem(self):
        return self.__dict__.popitem()

    def get(self, key, default=None):
        obj = self.__dict__.get(key)
        if obj is None:
            return default
        else:
            return obj

    def serialize(self) -> Dict[str, JSON]:
        return {k: v.serialize() if isinstance(v, Serializable) else v
                for k, v in self.__dict__.items()}

    @classmethod
    def deserialize(cls, data: Dict[str, JSON]) -> 'Obj':
        return cls(**data)


class Lst(list, GenericSerializable['Lst']):
    def __init__(self, iterable=()):
        list.__init__(self, (Obj(**x) if isinstance(x, dict)
                             else (Lst(x) if isinstance(x, list)
                                   else x) for x in iterable))

    def __repr__(self):
        return super().__repr__()

    def serialize(self) -> List[JSON]:
        return [v.serialize() if isinstance(v, Serializable) else v for v in self]

    @classmethod
    def deserialize(cls, data: List[JSON]) -> 'Lst':
        return cls(data)
