from typing import Dict, Type, TypeVar
import attr

T = TypeVar("T")


def dict_to_attrs(attrs_type: Type[T], data: Dict) -> T:
    fields = attr.fields_dict(attrs_type)
    new_items = {}
    for key, value in data.items():
        try:
            field = fields[key]
            new_items[key] = (dict_to_attrs(field.type, value)
                              if attr.has(field.type)
                              else value)
        except KeyError:
            del data[key]
    return attrs_type(**new_items)


def attrs_to_dict(data: T) -> Dict:
    return attr.asdict(data, recurse=True)
