# From https://github.com/Lonami/dumbot/blob/master/dumbot.py
# Modified to add Serializable base
from __future__ import annotations

from ..primitive import JSON
from .serializable import AbstractSerializable, Serializable


class Obj(AbstractSerializable):
    """"""

    def __init__(self, **kwargs):
        self.__dict__ = {
            k: Obj(**v) if isinstance(v, dict) else (Lst(v) if isinstance(v, list) else v)
            for k, v in kwargs.items()
        }

    def __getattr__(self, name):
        name = name.rstrip("_")
        obj = self.__dict__.get(name)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __getitem__(self, name):
        return self.__dict__.get(name)

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __str__(self):
        return str(self.serialize())

    def __repr__(self):
        return repr(self.serialize())

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__.update(state)

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

    def serialize(self) -> dict[str, JSON]:
        return {
            k: v.serialize() if isinstance(v, Serializable) else v
            for k, v in self.__dict__.items()
        }

    @classmethod
    def deserialize(cls, data: dict[str, JSON]) -> Obj:
        return cls(**data)


class Lst(list, AbstractSerializable):
    def __init__(self, iterable=()):
        list.__init__(
            self,
            (
                Obj(**x) if isinstance(x, dict) else (Lst(x) if isinstance(x, list) else x)
                for x in iterable
            ),
        )

    def __repr__(self):
        return super().__repr__()

    def serialize(self) -> list[JSON]:
        return [v.serialize() if isinstance(v, Serializable) else v for v in self]

    @classmethod
    def deserialize(cls, data: list[JSON]) -> Lst:
        return cls(data)
