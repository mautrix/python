# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod
import random
import string

import attr
from attr import dataclass

from mautrix.util.config import BaseFileConfig, ConfigUpdateHelper, yaml


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

    def check(self, config: 'BaseBridgeConfig') -> bool:
        if self.condition and not config[self.condition]:
            return False
        elif isinstance(self.value, ForbiddenKey):
            return str(self.value) in config[self.key]
        else:
            return config[self.key] == self.value

    @property
    def exception(self) -> ConfigValueError:
        return ConfigValueError(self.key, self.error)


class BaseBridgeConfig(BaseFileConfig, ABC):
    registration_path: str
    _registration: Optional[Dict]

    def __init__(self, path: str, registration_path: str, base_path: str) -> None:
        super().__init__(path, base_path)
        self.registration_path = registration_path
        self._registration = None

    def save(self) -> None:
        super().save()
        if self._registration and self.registration_path:
            with open(self.registration_path, "w") as stream:
                yaml.dump(self._registration, stream)

    @staticmethod
    def _new_token() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=64))

    @property
    def forbidden_defaults(self) -> List[ForbiddenDefault]:
        return [
            ForbiddenDefault("homeserver.address", "https://example.com"),
            ForbiddenDefault("homeserver.domain", "example.com"),
            ForbiddenDefault("appservice.as_token",
                             "This value is generated when generating the registration",
                             "Did you forget to generate the registration?"),
            ForbiddenDefault("appservice.hs_token",
                             "This value is generated when generating the registration",
                             "Did you forget to generate the registration?"),
        ]

    def check_default_values(self) -> None:
        for default in self.forbidden_defaults:
            if default.check(self):
                raise default.exception

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        copy = helper.copy

        copy("homeserver.address")
        copy("homeserver.domain")
        copy("homeserver.verify_ssl")

        copy("appservice.address")
        copy("appservice.hostname")
        copy("appservice.port")
        copy("appservice.max_body_size")

        copy("appservice.database")

        copy("appservice.id")
        copy("appservice.bot_username")
        copy("appservice.bot_displayname")
        copy("appservice.bot_avatar")

        copy("appservice.as_token")
        copy("appservice.hs_token")

        copy("logging")

    @property
    @abstractmethod
    def namespaces(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate the user ID and room alias namespace config for the registration as specified in
        https://matrix.org/docs/spec/application_service/r0.1.0.html#application-services
        """
        return {}

    def generate_registration(self) -> None:
        self["appservice.as_token"] = self._new_token()
        self["appservice.hs_token"] = self._new_token()

        self._registration = {
            "id": self["appservice.id"],
            "as_token": self["appservice.as_token"],
            "hs_token": self["appservice.hs_token"],
            "namespaces": self.namespaces,
            "url": self["appservice.address"],
            "sender_localpart": self["appservice.bot_username"],
            "rate_limited": False
        }
