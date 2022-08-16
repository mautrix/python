# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Awaitable, Iterator
from abc import ABC, abstractmethod
from itertools import chain
import asyncio
import hashlib
import hmac
import json
import logging

from aiohttp import ClientConnectionError
from yarl import URL

from mautrix.api import Path
from mautrix.appservice import AppService, IntentAPI
from mautrix.errors import (
    IntentError,
    MatrixError,
    MatrixInvalidToken,
    MatrixRequestError,
    WellKnownError,
)
from mautrix.types import (
    Event,
    EventFilter,
    EventType,
    Filter,
    FilterID,
    LoginType,
    PresenceState,
    RoomEventFilter,
    RoomFilter,
    RoomID,
    StateFilter,
    SyncToken,
    UserID,
)

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

    sync_with_custom_puppets: bool = True
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
    next_batch: SyncToken | None

    intent: IntentAPI

    _sync_task: asyncio.Task | None = None

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
        try:
            base_url = cls.homeserver_url_map[server]
        except KeyError:
            if server == cls.az.domain:
                base_url = cls.az.intent.api.base_url
            else:
                raise AutologinError(f"No homeserver URL configured for {server}")
        url = base_url / str(Path.v3.login)
        headers = {"Content-Type": "application/json"}
        login_req = {
            "initial_device_display_name": cls.login_device_name,
            "device_id": cls.login_device_name,
            "identifier": {
                "type": "m.id.user",
                "user": mxid,
            },
        }
        if secret == b"appservice":
            login_req["type"] = str(LoginType.APPSERVICE)
            headers["Authorization"] = f"Bearer {cls.az.as_token}"
        else:
            login_req["type"] = str(LoginType.PASSWORD)
            login_req["password"] = hmac.new(
                secret, mxid.encode("utf-8"), hashlib.sha512
            ).hexdigest()
        resp = await cls.az.http_session.post(url, data=json.dumps(login_req), headers=headers)
        data = await resp.json()
        try:
            return data["access_token"]
        except KeyError:
            error_msg = data.get("error", data.get("errcode", f"HTTP {resp.status}"))
            raise AutologinError(f"Didn't get an access token: {error_msg}") from None

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
            start_sync_task: Whether or not syncing should be started after logging in.
        """
        if access_token == "auto":
            access_token = await self._login_with_shared_secret(mxid)
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

        await self.start(start_sync_task=start_sync_task, check_e2ee_keys=True)

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
        self.next_batch = None
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
                await self.switch_mxid("auto", self.custom_mxid, start_sync_task=start_sync_task)
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
        if self.sync_with_custom_puppets and start_sync_task:
            if self._sync_task:
                self._sync_task.cancel()
            self.log.info(f"Initialized custom mxid: {whoami.user_id}. Starting sync task")
            self._sync_task = asyncio.create_task(self._try_sync())
        else:
            self.log.info(f"Initialized custom mxid: {whoami.user_id}. Not starting sync task")

    def stop(self) -> None:
        """Cancel the sync task."""
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None

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

    def _create_sync_filter(self) -> Awaitable[FilterID]:
        all_events = EventType.find("*")
        return self.intent.create_filter(
            Filter(
                account_data=EventFilter(types=[all_events]),
                presence=EventFilter(
                    types=[EventType.PRESENCE],
                    senders=[self.custom_mxid] if self.only_handle_own_synced_events else None,
                ),
                room=RoomFilter(
                    include_leave=False,
                    state=StateFilter(not_types=[all_events]),
                    timeline=RoomEventFilter(not_types=[all_events]),
                    account_data=RoomEventFilter(not_types=[all_events]),
                    ephemeral=RoomEventFilter(
                        types=[
                            EventType.TYPING,
                            EventType.RECEIPT,
                        ]
                    ),
                ),
            )
        )

    def _filter_events(self, room_id: RoomID, events: list[dict]) -> Iterator[Event]:
        for event in events:
            event["room_id"] = room_id
            if self.only_handle_own_synced_events:
                # We only want events about the custom puppet user, but we can't use
                # filters for typing and read receipt events.
                evt_type = EventType.find(event.get("type", None))
                event.setdefault("content", {})
                if evt_type == EventType.TYPING:
                    is_typing = self.custom_mxid in event["content"].get("user_ids", [])
                    event["content"]["user_ids"] = [self.custom_mxid] if is_typing else []
                elif evt_type == EventType.RECEIPT:
                    try:
                        event_id, receipt = event["content"].popitem()
                        data = receipt["m.read"][self.custom_mxid]
                        event["content"] = {event_id: {"m.read": {self.custom_mxid: data}}}
                    except KeyError:
                        continue
            yield event

    def _handle_sync(self, sync_resp: dict) -> None:
        # Get events from rooms -> join -> [room_id] -> ephemeral -> events (array)
        ephemeral_events = (
            event
            for room_id, data in sync_resp.get("rooms", {}).get("join", {}).items()
            for event in self._filter_events(room_id, data.get("ephemeral", {}).get("events", []))
        )

        # Get events from presence -> events (array)
        presence_events = sync_resp.get("presence", {}).get("events", [])

        # Deserialize and handle all events
        for event in chain(ephemeral_events, presence_events):
            asyncio.create_task(self.mx.try_handle_sync_event(Event.deserialize(event)))

    async def _try_sync(self) -> None:
        try:
            await self._sync()
        except asyncio.CancelledError:
            self.log.info(f"Syncing for {self.custom_mxid} cancelled")
        except Exception:
            self.log.critical(f"Fatal error syncing {self.custom_mxid}", exc_info=True)

    async def _sync(self) -> None:
        if not self.is_real_user:
            self.log.warning("Called sync() for non-custom puppet.")
            return
        custom_mxid: UserID = self.custom_mxid
        access_token_at_start: str = self.access_token
        errors: int = 0
        filter_id: FilterID = await self._create_sync_filter()
        self.log.debug(f"Starting syncer for {custom_mxid} with sync filter {filter_id}.")
        while access_token_at_start == self.access_token:
            try:
                cur_batch = self.next_batch
                sync_resp = await self.intent.sync(
                    filter_id=filter_id, since=cur_batch, set_presence=PresenceState.OFFLINE
                )
                try:
                    self.next_batch = sync_resp.get("next_batch", None)
                except Exception:
                    self.log.warning("Failed to store next batch", exc_info=True)
                errors = 0
                if cur_batch is not None:
                    self._handle_sync(sync_resp)
            except MatrixInvalidToken:
                # TODO when not using syncing, we should still check this occasionally and relogin
                self.log.warning(f"Access token for {custom_mxid} got invalidated, restarting...")
                await self.start(retry_auto_login=True, start_sync_task=False)
                if self.is_real_user:
                    self.log.info("Successfully relogined custom puppet, continuing sync")
                    filter_id = await self._create_sync_filter()
                    access_token_at_start = self.access_token
                else:
                    self.log.warning("Something went wrong during relogin")
                    raise
            except (MatrixError, ClientConnectionError, asyncio.TimeoutError) as e:
                errors += 1
                wait = min(errors, 11) ** 2
                self.log.warning(
                    f"Syncer for {custom_mxid} errored: {e}. Waiting for {wait} seconds..."
                )
                await asyncio.sleep(wait)
        self.log.debug(f"Syncer for custom puppet {custom_mxid} stopped.")
