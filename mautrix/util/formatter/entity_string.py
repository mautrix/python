# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Sequence, Union, Optional, Dict, Any

from attr import dataclass
import attr

from .formatted_string import FormattedString, EntityType


@dataclass
class Entity:
    type: EntityType
    offset: int
    length: int
    extra_info: Dict[str, Any] = attr.ib(factory=dict)

    def copy(self) -> 'Entity':
        return attr.evolve(self)

    def adjust_offset(self, offset: int, max_length: int = -1) -> Optional['Entity']:
        entity = attr.evolve(self, offset=self.offset + offset)
        if entity.offset < 0:
            entity.offset = 0
        elif entity.offset > max_length > -1:
            return None
        elif entity.offset + entity.length > max_length > -1:
            entity.length = max_length - entity.offset
        return entity


class EntityString(FormattedString):
    text: str
    entities: List[Entity]

    def __init__(self, text: str = "", entities: List[Entity] = None) -> None:
        self.text = text
        self.entities = entities or []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text='{self.text}', entities={self.entities})"

    def __str__(self) -> str:
        return self.text

    def _offset_entities(self, offset: int) -> 'EntityString':
        if offset == 0:
            return self
        self.entities = [entity.adjust_offset(offset, len(self.text))
                         for entity in self.entities if entity
                         if entity.offset + offset <= len(self.text)]
        return self

    def append(self, *args: Union[str, 'FormattedString']) -> 'EntityString':
        for msg in args:
            if isinstance(msg, EntityString):
                self.entities += [entity.adjust_offset(len(self.text)) for entity in msg.entities]
                self.text += msg.text
            else:
                self.text += str(msg)
        return self

    def prepend(self, *args: Union[str, 'FormattedString']) -> 'EntityString':
        for msg in args:
            if isinstance(msg, EntityString):
                self.text = msg.text + self.text
                self.entities = msg.entities + [entity.adjust_offset(len(msg.text))
                                                for entity in self.entities]
            else:
                text = str(msg)
                self.text = text + self.text
                self.entities = [entity.adjust_offset(len(text)) for entity in self.entities]
        return self

    def format(self, entity_type: EntityType, offset: int = None, length: int = None, **kwargs
               ) -> 'EntityString':
        self.entities.append(Entity(type=entity_type, offset=offset or 0,
                                    length=length or len(self.text), extra_info=kwargs))
        return self

    def trim(self) -> 'EntityString':
        orig_len = len(self.text)
        self.text = self.text.lstrip()
        diff = orig_len - len(self.text)
        self.text = self.text.rstrip()
        self._offset_entities(-diff)
        return self

    def split(self, separator, max_items: int = -1) -> List['EntityString']:
        text_parts = self.text.split(separator, max_items - 1)
        output: List[EntityString] = []

        offset = 0
        for part in text_parts:
            msg = type(self)(part)
            for entity in self.entities:
                start_in_range = len(part) > entity.offset - offset >= 0
                end_in_range = len(part) >= entity.offset - offset + entity.length > 0
                if start_in_range and end_in_range:
                    msg.entities.append(entity.adjust_offset(-offset))
            output.append(msg)

            offset += len(part)
            offset += len(separator)

        return output

    @classmethod
    def join(cls, items: Sequence[Union[str, 'EntityString']],
             separator: str = " ") -> 'EntityString':
        main = cls()
        for msg in items:
            if not isinstance(msg, EntityString):
                msg = cls(text=str(msg))
            main.entities += [entity.adjust_offset(len(main.text)) for entity in msg.entities]
            main.text += msg.text + separator
        if len(separator) > 0:
            main.text = main.text[:-len(separator)]
        return main
