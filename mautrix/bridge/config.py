# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
from abc import ABC
import re
import secrets
import time

from mautrix.util.config import (
    BaseFileConfig,
    BaseValidatableConfig,
    ConfigUpdateHelper,
    ForbiddenDefault,
    yaml,
)


class BaseBridgeConfig(BaseFileConfig, BaseValidatableConfig, ABC):
    registration_path: str
    _registration: dict | None
    _check_tokens: bool

    def __init__(self, path: str, registration_path: str, base_path: str) -> None:
        super().__init__(path, base_path)
        self.registration_path = registration_path
        self._registration = None
        self._check_tokens = True

    def save(self) -> None:
        super().save()
        if self._registration and self.registration_path:
            with open(self.registration_path, "w") as stream:
                yaml.dump(self._registration, stream)

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(48)

    @property
    def forbidden_defaults(self) -> list[ForbiddenDefault]:
        return [
            ForbiddenDefault("homeserver.address", "https://example.com"),
            ForbiddenDefault("homeserver.domain", "example.com"),
        ] + (
            [
                ForbiddenDefault(
                    "appservice.as_token",
                    "This value is generated when generating the registration",
                    "Did you forget to generate the registration?",
                ),
                ForbiddenDefault(
                    "appservice.hs_token",
                    "This value is generated when generating the registration",
                    "Did you forget to generate the registration?",
                ),
            ]
            if self._check_tokens
            else []
        )

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        copy, copy_dict = helper.copy, helper.copy_dict

        copy("homeserver.address")
        copy("homeserver.domain")
        copy("homeserver.verify_ssl")
        copy("homeserver.http_retry_count")
        copy("homeserver.connection_limit")
        copy("homeserver.status_endpoint")
        copy("homeserver.message_send_checkpoint_endpoint")

        copy("appservice.address")
        copy("appservice.hostname")
        copy("appservice.port")
        copy("appservice.max_body_size")

        copy("appservice.tls_cert")
        copy("appservice.tls_key")

        copy("appservice.database")
        copy("appservice.database_opts")

        copy("appservice.id")
        copy("appservice.bot_username")
        copy("appservice.bot_displayname")
        copy("appservice.bot_avatar")

        copy("appservice.as_token")
        copy("appservice.hs_token")

        copy("appservice.ephemeral_events")

        copy("bridge.management_room_text.welcome")
        copy("bridge.management_room_text.welcome_connected")
        copy("bridge.management_room_text.welcome_unconnected")
        copy("bridge.management_room_text.additional_help")
        copy("bridge.management_room_multiple_messages")

        copy("bridge.relay.enabled")
        copy_dict("bridge.relay.message_formats", override_existing_map=False)

        copy("manhole.enabled")
        copy("manhole.path")
        copy("manhole.whitelist")

        copy("logging")

    @property
    def namespaces(self) -> dict[str, list[dict[str, Any]]]:
        """
        Generate the user ID and room alias namespace config for the registration as specified in
        https://matrix.org/docs/spec/application_service/r0.1.0.html#application-services
        """
        homeserver = self["homeserver.domain"]
        regex_ph = f"regexplaceholder{int(time.time())}"
        username_format = self["bridge.username_template"].format(userid=regex_ph)
        alias_format = (
            self["bridge.alias_template"].format(groupname=regex_ph)
            if "bridge.alias_template" in self
            else None
        )
        group_id = (
            {"group_id": self["appservice.community_id"]}
            if self["appservice.community_id"]
            else {}
        )

        return {
            "users": [
                {
                    "exclusive": True,
                    "regex": re.escape(f"@{username_format}:{homeserver}").replace(regex_ph, ".*"),
                    **group_id,
                }
            ],
            "aliases": [
                {
                    "exclusive": True,
                    "regex": re.escape(f"#{alias_format}:{homeserver}").replace(regex_ph, ".*"),
                }
            ]
            if alias_format
            else [],
        }

    def generate_registration(self) -> None:
        self["appservice.as_token"] = self._new_token()
        self["appservice.hs_token"] = self._new_token()

        namespaces = self.namespaces
        bot_username = self["appservice.bot_username"]
        homeserver_domain = self["homeserver.domain"]
        namespaces.setdefault("users", []).append(
            {
                "exclusive": True,
                "regex": re.escape(f"@{bot_username}:{homeserver_domain}"),
            }
        )

        self._registration = {
            "id": self["appservice.id"],
            "as_token": self["appservice.as_token"],
            "hs_token": self["appservice.hs_token"],
            "namespaces": namespaces,
            "url": self["appservice.address"],
            "sender_localpart": self._new_token(),
            "rate_limited": False,
        }

        if self["appservice.ephemeral_events"]:
            self._registration["de.sorunome.msc2409.push_ephemeral"] = True
            self._registration["push_ephemeral"] = True
