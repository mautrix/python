# From https://github.com/Lonami/dumbot/blob/master/dumbot.py


class Obj:
    def __init__(self, **kwargs):
        self.__dict__ = {k: Obj(**v) if isinstance(v, dict) else (
            Lst(v) if isinstance(v, list) else v) for k, v in kwargs.items()}

    def __getattr__(self, name):
        name = name.rstrip('_')
        obj = self.__dict__.get(name)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __getitem__(self, name):
        obj = self.__dict__.get(name)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __iter__(self):
        return iter(())

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return repr(self.to_dict())

    def __bool__(self):
        return bool(self.__dict__)

    def __contains__(self, item):
        return item in self.__dict__

    def __call__(self, *a, **kw):
        return Obj()

    def to_dict(self):
        return {k: v.to_dict() if isinstance(v, Obj) else v
                for k, v in self.__dict__.items()}


class Lst(list):
    def __init__(self, iterable=()):
        list.__init__(self, (Obj(**x) if isinstance(x, dict) else (
            Lst(x) if isinstance(x, list) else x) for x in iterable))

    def __getattr__(self, name):
        name = name.rstrip('_')
        obj = self.__dict__.get(name)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __repr__(self):
        return super().__repr__() + repr(self.to_dict())

    def to_dict(self):
        return {k: v.to_dict() if isinstance(v, Obj) else v
                for k, v in self.__dict__.items()}
