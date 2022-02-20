# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
from abc import ABC, abstractmethod

from attr import dataclass
import attr

from .base import BaseConfig


class ConfigValueError(ValueError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(
            f"{key} not configured. {message}" if message else f"{key} not configured"
        )


class ForbiddenKey(str):
    pass


@dataclass
class ForbiddenDefault:
    key: str
    value: Any
    error: str | None = None
    condition: str | None = attr.ib(default=None, kw_only=True)

    def check(self, config: BaseConfig) -> bool:
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
    def forbidden_defaults(self) -> list[ForbiddenDefault]:
        pass

    def check_default_values(self) -> None:
        for default in self.forbidden_defaults:
            if default.check(self):
                raise default.exception
