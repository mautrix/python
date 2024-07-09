# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import hashlib
import hmac
import logging

from yarl import URL

from mautrix.appservice import AppService, IntentAPI
from mautrix.client import ClientAPI
from mautrix.errors import (
    IntentError,
    MatrixError,
    MatrixInvalidToken,
    MatrixRequestError,
    WellKnownError,
)
from mautrix.types import LoginType, MatrixUserIdentifier, RoomID, UserID

from .. import bridge as br


class CustomPuppetError(MatrixError):
    """Base class for double puppeting setup errors."""


class InvalidAccessToken(CustomPuppetError):
    def __init__(self):
        super().__init__("The given access token was invalid.")


class OnlyLoginSelf(CustomPuppetError):
    def __init__(self):
        super().__init__("You may only enable double puppeting with your own Matrix account.")


class EncryptionKeysFound(CustomPuppetError):
    def __init__(self):
        super().__init__(
            "The given access token is for a device that has encryption keys set up. "
            "Please provide a fresh token, don't reuse one from another client."
        )


class HomeserverURLNotFound(CustomPuppetError):
    def __init__(self, domain: str):
        super().__init__(
            f"Could not discover a valid homeserver URL for {domain}."
            " Please ensure a client .well-known file is set up, or ask the bridge administrator "
            "to add the homeserver URL to the bridge config."
        )


class OnlyLoginTrustedDomain(CustomPuppetError):
    def __init__(self):
        super().__init__(
            "This bridge doesn't allow double-puppeting with accounts on untrusted servers."
        )


class AutologinError(CustomPuppetError):
    pass


class CustomPuppetMixin(ABC):
    """
    Mixin for the Puppet class to enable Matrix puppeting.

    Attributes:
        sync_with_custom_puppets: Whether or not custom puppets should /sync
        allow_discover_url: Allow logging into other homeservers using .well-known discovery.
        homeserver_url_map: Static map from server name to URL that are always allowed to log in.
        only_handle_own_synced_events: Whether or not typing notifications and read receipts by
                                       other users should be filtered away before passing them to
                                       the Matrix event handler.

        az: The AppService object.
        loop: The asyncio event loop.
        log: The logger to use.
        mx: The Matrix event handler to send /sync events to.

        by_custom_mxid: A mapping from custom mxid to puppet object.

        default_mxid: The default user ID of the puppet.
        default_mxid_intent: The IntentAPI for the default user ID.
        custom_mxid: The user ID of the custom puppet.
        access_token: The access token for the custom puppet.

        intent: The primary IntentAPI.
    """

    allow_discover_url: bool = False
    homeserver_url_map: dict[str, URL] = {}
    only_handle_own_synced_events: bool = True
    login_shared_secret_map: dict[str, bytes] = {}
    login_device_name: str | None = None

    az: AppService
    loop: asyncio.AbstractEventLoop
    log: logging.Logger
    mx: br.BaseMatrixHandler

    by_custom_mxid: dict[UserID, CustomPuppetMixin] = {}

    default_mxid: UserID
    default_mxid_intent: IntentAPI
    custom_mxid: UserID | None
    access_token: str | None
    base_url: URL | None

    intent: IntentAPI

    @abstractmethod
    async def save(self) -> None:
        """Save the information of this puppet. Called from :meth:`switch_mxid`"""

    @property
    def mxid(self) -> UserID:
        """The main Matrix user ID of this puppet."""
        return self.custom_mxid or self.default_mxid

    @property
    def is_real_user(self) -> bool:
        """Whether this puppet uses a real Matrix user instead of an appservice-owned ID."""
        return bool(self.custom_mxid and self.access_token)

    def _fresh_intent(self) -> IntentAPI:
        if self.custom_mxid:
            _, server = self.az.intent.parse_user_id(self.custom_mxid)
            try:
                self.base_url = self.homeserver_url_map[server]
            except KeyError:
                if server == self.az.domain:
                    self.base_url = self.az.intent.api.base_url
        if self.access_token == "appservice-config" and self.custom_mxid:
            try:
                secret = self.login_shared_secret_map[server]
            except KeyError:
                raise AutologinError(f"No shared secret configured for {server}")
            self.log.debug(f"Using as_token for double puppeting {self.custom_mxid}")
            return self.az.intent.user(
                self.custom_mxid,
                secret.decode("utf-8").removeprefix("as_token:"),
                self.base_url,
                as_token=True,
            )
        return (
            self.az.intent.user(self.custom_mxid, self.access_token, self.base_url)
            if self.is_real_user
            else self.default_mxid_intent
        )

    @classmethod
    def can_auto_login(cls, mxid: UserID) -> bool:
        _, server = cls.az.intent.parse_user_id(mxid)
        return server in cls.login_shared_secret_map and (
            server in cls.homeserver_url_map or server == cls.az.domain
        )

    @classmethod
    async def _login_with_shared_secret(cls, mxid: UserID) -> str:
        _, server = cls.az.intent.parse_user_id(mxid)
        try:
            secret = cls.login_shared_secret_map[server]
        except KeyError:
            raise AutologinError(f"No shared secret configured for {server}")
        if secret.startswith(b"as_token:"):
            return "appservice-config"
        try:
            base_url = cls.homeserver_url_map[server]
        except KeyError:
            if server == cls.az.domain:
                base_url = cls.az.intent.api.base_url
            else:
                raise AutologinError(f"No homeserver URL configured for {server}")
        client = ClientAPI(base_url=base_url)
        login_args = {}
        if secret == b"appservice":
            login_type = LoginType.APPSERVICE
            client.api.token = cls.az.as_token
        else:
            flows = await client.get_login_flows()
            flow = flows.get_first_of_type(LoginType.DEVTURE_SHARED_SECRET, LoginType.PASSWORD)
            if not flow:
                raise AutologinError("No supported shared secret auth login flows")
            login_type = flow.type
            token = hmac.new(secret, mxid.encode("utf-8"), hashlib.sha512).hexdigest()
            if login_type == LoginType.DEVTURE_SHARED_SECRET:
                login_args["token"] = token
            elif login_type == LoginType.PASSWORD:
                login_args["password"] = token
        resp = await client.login(
            identifier=MatrixUserIdentifier(user=mxid),
            device_id=cls.login_device_name,
            initial_device_display_name=cls.login_device_name,
            login_type=login_type,
            **login_args,
            store_access_token=False,
            update_hs_url=False,
        )
        return resp.access_token

    async def switch_mxid(
        self, access_token: str | None, mxid: UserID | None, start_sync_task: bool = True
    ) -> None:
        """
        Switch to a real Matrix user or away from one.

        Args:
            access_token: The access token for the custom account, or ``None`` to switch back to
                          the appservice-owned ID.
            mxid: The expected Matrix user ID of the custom account, or ``None`` when
                  ``access_token`` is None.
        """
        if access_token == "auto":
            access_token = await self._login_with_shared_secret(mxid)
            if access_token != "appservice-config":
                self.log.debug(f"Logged in for {mxid} using shared secret")

        if mxid is not None:
            _, mxid_domain = self.az.intent.parse_user_id(mxid)
            if mxid_domain in self.homeserver_url_map:
                base_url = self.homeserver_url_map[mxid_domain]
            elif mxid_domain == self.az.domain:
                base_url = None
            else:
                if not self.allow_discover_url:
                    raise OnlyLoginTrustedDomain()
                try:
                    base_url = await IntentAPI.discover(mxid_domain, self.az.http_session)
                except WellKnownError as e:
                    raise HomeserverURLNotFound(mxid_domain) from e
                if base_url is None:
                    raise HomeserverURLNotFound(mxid_domain)
        else:
            base_url = None

        prev_mxid = self.custom_mxid
        self.custom_mxid = mxid
        self.access_token = access_token
        self.base_url = base_url
        self.intent = self._fresh_intent()

        await self.start(check_e2ee_keys=True)

        try:
            del self.by_custom_mxid[prev_mxid]
        except KeyError:
            pass
        if self.mxid != self.default_mxid:
            self.by_custom_mxid[self.mxid] = self
            try:
                await self._leave_rooms_with_default_user()
            except Exception:
                self.log.warning("Error when leaving rooms with default user", exc_info=True)
        await self.save()

    async def try_start(self, retry_auto_login: bool = True) -> None:
        try:
            await self.start(retry_auto_login=retry_auto_login)
        except Exception:
            self.log.exception("Failed to initialize custom mxid")

    async def _invalidate_double_puppet(self) -> None:
        if self.custom_mxid and self.by_custom_mxid.get(self.custom_mxid) == self:
            del self.by_custom_mxid[self.custom_mxid]
        self.custom_mxid = None
        self.access_token = None
        await self.save()
        self.intent = self._fresh_intent()

    async def start(
        self,
        retry_auto_login: bool = False,
        start_sync_task: bool = True,
        check_e2ee_keys: bool = False,
    ) -> None:
        """Initialize the custom account this puppet uses. Should be called at startup to start
        the /sync task. Is called by :meth:`switch_mxid` automatically."""
        if not self.is_real_user:
            return

        try:
            whoami = await self.intent.whoami()
        except MatrixInvalidToken as e:
            if retry_auto_login and self.custom_mxid and self.can_auto_login(self.custom_mxid):
                self.log.debug(f"Got {e.errcode} while trying to initialize custom mxid")
                await self.switch_mxid("auto", self.custom_mxid)
                return
            self.log.warning(f"Got {e.errcode} while trying to initialize custom mxid")
            whoami = None
        if not whoami or whoami.user_id != self.custom_mxid:
            prev_custom_mxid = self.custom_mxid
            await self._invalidate_double_puppet()
            if whoami and whoami.user_id != prev_custom_mxid:
                raise OnlyLoginSelf()
            raise InvalidAccessToken()
        if check_e2ee_keys:
            try:
                devices = await self.intent.query_keys({whoami.user_id: [whoami.device_id]})
                device_keys = devices.device_keys.get(whoami.user_id, {}).get(whoami.device_id)
            except Exception:
                self.log.warning(
                    "Failed to query keys to check if double puppeting token was reused",
                    exc_info=True,
                )
            else:
                if device_keys and len(device_keys.keys) > 0:
                    await self._invalidate_double_puppet()
                    raise EncryptionKeysFound()
        self.log.info(f"Initialized custom mxid: {whoami.user_id}")

    def stop(self) -> None:
        """
        No-op

        .. deprecated:: 0.20.1
        """

    async def default_puppet_should_leave_room(self, room_id: RoomID) -> bool:
        """
        Whether or not the default puppet user should leave the given room when this puppet is
        switched to using a custom user account.

        Args:
            room_id: The room to check.

        Returns:
            Whether or not the default user account should leave.
        """
        return True

    async def _leave_rooms_with_default_user(self) -> None:
        for room_id in await self.default_mxid_intent.get_joined_rooms():
            try:
                if await self.default_puppet_should_leave_room(room_id):
                    await self.default_mxid_intent.leave_room(room_id)
                    await self.intent.ensure_joined(room_id)
            except (IntentError, MatrixRequestError):
                pass
