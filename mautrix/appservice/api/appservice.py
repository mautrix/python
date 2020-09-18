# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, Awaitable, Union, Any, TYPE_CHECKING
from datetime import datetime, timezone
import asyncio

from aiohttp import ClientSession
from yarl import URL

from mautrix.types import UserID
from mautrix.api import HTTPAPI, Method, PathBuilder
from mautrix.util.logging import TraceLogger

from .intent import IntentAPI

if TYPE_CHECKING:
    from ..state_store import ASStateStore


class AppServiceAPI(HTTPAPI):
    """
    AppServiceAPI is an extension to HTTPAPI that provides appservice-specific features,
    such as child instances and easy access to IntentAPIs.
    """
    base_log: TraceLogger

    identity: Optional[UserID]
    bot_mxid: UserID

    state_store: 'ASStateStore'
    txn_id: int
    children: Dict[str, 'ChildAppServiceAPI']
    real_users: Dict[str, 'AppServiceAPI']

    is_real_user: bool
    real_user_content_key: Optional[str]

    _bot_intent: Optional[IntentAPI]

    def __init__(self, base_url: Union[URL, str], bot_mxid: UserID = None, token: str = None,
                 identity: Optional[UserID] = None, log: TraceLogger = None,
                 state_store: 'ASStateStore' = None, client_session: ClientSession = None,
                 child: bool = False, real_user: bool = False,
                 real_user_content_key: Optional[str] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
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
            real_user_content_key: The key to inject in outgoing message events sent through real
                users.
        """
        self.base_log = log
        api_log = self.base_log.getChild("api").getChild(identity or "bot")
        super().__init__(base_url=base_url, token=token, loop=loop, log=api_log,
                         client_session=client_session, txn_id=0 if not child else None)
        self.identity = identity
        self.bot_mxid = bot_mxid
        self._bot_intent = None
        self.state_store = state_store
        self.is_real_user = real_user
        self.real_user_content_key = real_user_content_key

        if not child:
            self.txn_id = 0
            if not real_user:
                self.children = {}
                self.real_users = {}

    def user(self, user: UserID) -> 'ChildAppServiceAPI':
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

    def real_user(self, mxid: UserID, token: str, base_url: Optional[URL] = None
                  ) -> 'AppServiceAPI':
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
            child = type(self)(base_url=base_url or self.base_url, token=token, identity=mxid,
                               log=self.base_log, state_store=self.state_store,
                               client_session=self.session, real_user=True,
                               real_user_content_key=self.real_user_content_key, loop=self.loop)
            self.real_users[mxid] = child
        return child

    def bot_intent(self) -> 'IntentAPI':
        """
        Get the intent API for the appservice bot.

        Returns:
            The IntentAPI object for the appservice bot
        """
        if not self._bot_intent:
            self._bot_intent = IntentAPI(self.bot_mxid, self, state_store=self.state_store)
        return self._bot_intent

    def intent(self, user: UserID = None, token: Optional[str] = None,
               base_url: Optional[str] = None) -> 'IntentAPI':
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
            return IntentAPI(user, self.real_user(user, token, base_url), self.bot_intent(),
                             self.state_store)
        return IntentAPI(user, self.user(user), self.bot_intent(), self.state_store)

    def request(self, method: Method, path: PathBuilder,
                content: Optional[Union[Dict, bytes, str]] = None, timestamp: Optional[int] = None,
                headers: Optional[Dict[str, str]] = None,
                query_params: Optional[Dict[str, Any]] = None) -> Awaitable[Dict]:
        """
        Make a raw HTTP request, with optional AppService timestamp massaging and external_url
        setting.

        Args:
            method: The HTTP method to use.
            path: The API endpoint to call.
                Does not include the base path (e.g. /_matrix/client/r0).
            content: The content to post as a dict (json) or bytes/str (raw).
            timestamp: The timestamp query param used for timestamp massaging.
            headers: The dict of HTTP headers to send.
            query_params: The dict of query parameters to send.

        Returns:
            The response as a dict.
        """
        query_params = query_params or {}
        if timestamp is not None:
            if isinstance(timestamp, datetime):
                timestamp = int(timestamp.replace(tzinfo=timezone.utc).timestamp() * 1000)
            query_params["ts"] = timestamp
        if not self.is_real_user:
            query_params["user_id"] = self.identity or self.bot_mxid

        return super().request(method, path, content, headers, query_params)


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
        super().__init__(parent.base_url, parent.bot_mxid, parent.token, user, parent.base_log,
                         parent.state_store, parent.session, child=True, loop=parent.loop,
                         real_user_content_key=parent.real_user_content_key)
        self.parent = parent

    @property
    def txn_id(self) -> int:
        return self.parent.txn_id

    @txn_id.setter
    def txn_id(self, value: int) -> None:
        self.parent.txn_id = value
