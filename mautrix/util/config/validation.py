# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, List, Any
from abc import ABC, abstractmethod

import attr
from attr import dataclass

from .base import BaseConfig


class ConfigValueError(ValueError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key} not configured. {message}" if message else f"{key} not configured")


class ForbiddenKey(str):
    pass


@dataclass
class ForbiddenDefault:
    key: str
    value: Any
    error: Optional[str] = None
    condition: Optional[str] = attr.ib(default=None, kw_only=True)

    def check(self, config: 'BaseConfig') -> bool:
        if self.condition and not config[self.condition]:
            return False
        elif isinstance(self.value, ForbiddenKey):
            return str(self.value) in config[self.key]
        else:
            return config[self.key] == self.value

    @property
    def exception(self) -> ConfigValueError:
        return ConfigValueError(self.key, self.error)


class BaseValidatableConfig(BaseConfig, ABC):
    @property
    @abstractmethod
    def forbidden_defaults(self) -> List[ForbiddenDefault]:
        pass

    def check_default_values(self) -> None:
        for default in self.forbidden_defaults:
            if default.check(self):
                raise default.exception
