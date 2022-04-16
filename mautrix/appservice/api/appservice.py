# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable
from datetime import datetime, timezone
import asyncio

from aiohttp import ClientSession
from yarl import URL

from mautrix.api import HTTPAPI, Method, PathBuilder
from mautrix.types import UserID
from mautrix.util.logging import TraceLogger

from .. import api as as_api, state_store as ss


class AppServiceAPI(HTTPAPI):
    """
    AppServiceAPI is an extension to HTTPAPI that provides appservice-specific features,
    such as child instances and easy access to IntentAPIs.
    """

    base_log: TraceLogger

    identity: UserID | None
    bot_mxid: UserID

    state_store: ss.ASStateStore
    txn_id: int
    children: dict[str, ChildAppServiceAPI]
    real_users: dict[str, AppServiceAPI]

    is_real_user: bool
    bridge_name: str | None

    _bot_intent: as_api.IntentAPI | None

    def __init__(
        self,
        base_url: URL | str,
        bot_mxid: UserID = None,
        token: str = None,
        identity: UserID | None = None,
        log: TraceLogger = None,
        state_store: ss.ASStateStore = None,
        client_session: ClientSession = None,
        child: bool = False,
        real_user: bool = False,
        bridge_name: str | None = None,
        default_retry_count: int = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """
        Args:
            base_url: The base URL of the homeserver client-server API to use.
            bot_mxid: The Matrix user ID of the appservice bot.
            token: The access token to use.
            identity: The ID of the Matrix user to act as.
            log: The logging.Logger instance to log requests with.
            state_store: The StateStore instance to use.
            client_session: The aiohttp ClientSession to use.
            child: Whether or not this is instance is a child of another AppServiceAPI.
            real_user: Whether or not this is a real (non-appservice-managed) user.
            bridge_name: The name of the bridge to put in the ``fi.mau.double_puppet_source`` field
                in outgoing message events sent through real users.
        """
        self.base_log = log
        api_log = self.base_log.getChild("api").getChild(identity or "bot")
        super().__init__(
            base_url=base_url,
            token=token,
            loop=loop,
            log=api_log,
            client_session=client_session,
            txn_id=0 if not child else None,
            default_retry_count=default_retry_count,
        )
        self.identity = identity
        self.bot_mxid = bot_mxid
        self._bot_intent = None
        self.state_store = state_store
        self.is_real_user = real_user
        self.bridge_name = bridge_name

        if not child:
            self.txn_id = 0
            if not real_user:
                self.children = {}
                self.real_users = {}

    def user(self, user: UserID) -> ChildAppServiceAPI:
        """
        Get the AppServiceAPI for an appservice-managed user.

        Args:
            user: The Matrix user ID of the user whose AppServiceAPI to get.

        Returns:
            The ChildAppServiceAPI object for the user.
        """
        if self.is_real_user:
            raise ValueError("Can't get child of real user")

        try:
            return self.children[user]
        except KeyError:
            child = ChildAppServiceAPI(user, self)
            self.children[user] = child
            return child

    def real_user(self, mxid: UserID, token: str, base_url: URL | None = None) -> AppServiceAPI:
        """
        Get the AppServiceAPI for a real (non-appservice-managed) Matrix user.

        Args:
            mxid: The Matrix user ID of the user whose AppServiceAPI to get.
            token: The access token for the user.
            base_url: The base URL of the homeserver client-server API to use. Defaults to the
                appservice homeserver URL.

        Returns:
            The AppServiceAPI object for the user.

        Raises:
            ValueError: When this AppServiceAPI instance is a real user.
        """
        if self.is_real_user:
            raise ValueError("Can't get child of real user")

        try:
            child = self.real_users[mxid]
            child.base_url = base_url or child.base_url
            child.token = token or child.token
        except KeyError:
            child = type(self)(
                base_url=base_url or self.base_url,
                token=token,
                identity=mxid,
                log=self.base_log,
                state_store=self.state_store,
                client_session=self.session,
                real_user=True,
                bridge_name=self.bridge_name,
                default_retry_count=self.default_retry_count,
            )
            self.real_users[mxid] = child
        return child

    def bot_intent(self) -> as_api.IntentAPI:
        """
        Get the intent API for the appservice bot.

        Returns:
            The IntentAPI object for the appservice bot
        """
        if not self._bot_intent:
            self._bot_intent = as_api.IntentAPI(self.bot_mxid, self, state_store=self.state_store)
        return self._bot_intent

    def intent(
        self, user: UserID = None, token: str | None = None, base_url: str | None = None
    ) -> as_api.IntentAPI:
        """
        Get the intent API of a child user.

        Args:
            user: The Matrix user ID whose intent API to get.
            token: The access token to use. Only applicable for non-appservice-managed users.
            base_url: The base URL of the homeserver client-server API to use. Only applicable for
                non-appservice users. Defaults to the appservice homeserver URL.

        Returns:
            The IntentAPI object for the given user.

        Raises:
            ValueError: When this AppServiceAPI instance is a real user.
        """
        if self.is_real_user:
            raise ValueError("Can't get child intent of real user")
        if token:
            return as_api.IntentAPI(
                user, self.real_user(user, token, base_url), self.bot_intent(), self.state_store
            )
        return as_api.IntentAPI(user, self.user(user), self.bot_intent(), self.state_store)

    def request(
        self,
        method: Method,
        path: PathBuilder,
        content: dict | bytes | str | None = None,
        timestamp: int | None = None,
        headers: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
        retry_count: int | None = None,
        metrics_method: str | None = "",
        min_iter_size: int = 25 * 1024 * 1024,
    ) -> Awaitable[dict]:
        """
        Make a raw Matrix API request, acting as the appservice user assigned to this AppServiceAPI
        instance and optionally including timestamp massaging.

        Args:
            method: The HTTP method to use.
            path: The full API endpoint to call (including the _matrix/... prefix)
            content: The content to post as a dict/list (will be serialized as JSON)
                     or bytes/str (will be sent as-is).
            timestamp: The timestamp query param used for timestamp massaging.
            headers: A dict of HTTP headers to send. If the headers don't contain ``Content-Type``,
                     it'll be set to ``application/json``. The ``Authorization`` header is always
                     overridden if :attr:`token` is set.
            query_params: A dict of query parameters to send.
            retry_count: Number of times to retry if the homeserver isn't reachable.
                         Defaults to :attr:`default_retry_count`.
            metrics_method: Name of the method to include in Prometheus timing metrics.
            min_iter_size: If the request body is larger than this value, it will be passed to
                           aiohttp as an async iterable to stop it from copying the whole thing
                           in memory.

        Returns:
            The parsed response JSON.
        """
        query_params = query_params or {}
        if timestamp is not None:
            if isinstance(timestamp, datetime):
                timestamp = int(timestamp.replace(tzinfo=timezone.utc).timestamp() * 1000)
            query_params["ts"] = timestamp
        if not self.is_real_user:
            query_params["user_id"] = self.identity or self.bot_mxid

        return super().request(
            method, path, content, headers, query_params, retry_count, metrics_method
        )


class ChildAppServiceAPI(AppServiceAPI):
    """
    ChildAppServiceAPI is a simple way to copy AppServiceAPIs while maintaining a shared txn_id.
    """

    parent: AppServiceAPI

    def __init__(self, user: UserID, parent: AppServiceAPI) -> None:
        """
        Args:
            user: The Matrix user ID of the child user.
            parent: The parent AppServiceAPI instance.
        """
        super().__init__(
            parent.base_url,
            parent.bot_mxid,
            parent.token,
            user,
            parent.base_log,
            parent.state_store,
            parent.session,
            child=True,
            bridge_name=parent.bridge_name,
            default_retry_count=parent.default_retry_count,
        )
        self.parent = parent

    @property
    def txn_id(self) -> int:
        return self.parent.txn_id

    @txn_id.setter
    def txn_id(self, value: int) -> None:
        self.parent.txn_id = value
