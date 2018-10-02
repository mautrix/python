from typing import Optional, Dict, Awaitable, Union, Any, TYPE_CHECKING
from datetime import datetime, timezone

from ...api import HTTPAPI
from .intent import IntentAPI

if TYPE_CHECKING:
    from logging import Logger
    from aiohttp import ClientSession
    from ..state_store import StateStore


class AppServiceAPI(HTTPAPI):
    """
    AppServiceAPI is an extension to HTTPAPI that provides appservice-specific features,
    such as child instances and easy access to IntentAPIs.
    """

    def __init__(self, base_url: str, bot_mxid: str = None, token: str = None,
                 identity: Optional[str] = None, log: 'Logger' = None,
                 state_store: 'StateStore' = None, client_session: 'ClientSession' = None,
                 child: bool = False, real_user: bool = False,
                 real_user_content_key: Optional[str] = None) -> None:
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
        super().__init__(base_url=base_url, token=token,
                         log=log if real_user or child else log.getChild("api"),
                         client_session=client_session, txn_id=0 if not child else None)
        self.identity: str = identity
        self.bot_mxid: str = bot_mxid
        self._bot_intent: Optional[IntentAPI] = None
        self.state_store: 'StateStore' = state_store
        self.is_real_user: bool = real_user
        self.real_user_content_key: Optional[str] = real_user_content_key

        if not child:
            self.txn_id: int = 0
            self.intent_log: 'Logger' = log.getChild("intent")
            if not real_user:
                self.children: Dict[str, 'ChildAppServiceAPI'] = {}
                self.real_users: Dict[str, 'AppServiceAPI'] = {}

    def user(self, user: str) -> 'ChildAppServiceAPI':
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

    def real_user(self, mxid: str, token: str, base_url: Optional[str] = None) -> 'AppServiceAPI':
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
            return self.real_users[mxid]
        except KeyError:
            child = self.__class__(base_url or self.base_url, token, mxid, self.log,
                                   self.state_store, self.session, real_user=True,
                                   real_user_content_key=self.real_user_content_key)
            self.real_users[mxid] = child
            return child

    def bot_intent(self) -> 'IntentAPI':
        """
        Get the intent API for the appservice bot.

        Returns:
            The IntentAPI object for the appservice bot
        """
        if not self._bot_intent:
            self._bot_intent = IntentAPI(self.bot_mxid, self, state_store=self.state_store,
                                         log=self.intent_log)
        return self._bot_intent

    def intent(self, user: str = None, token: Optional[str] = None, base_url: Optional[str] = None
               ) -> 'IntentAPI':
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
                             self.state_store, self.intent_log)
        return IntentAPI(user, self.user(user), self.bot_intent(), self.state_store,
                         self.intent_log)

    def request(self, method: str, path: str, content: Optional[Union[Dict, bytes, str]] = None,
                timestamp: Optional[int] = None, external_url: Optional[str] = None,
                headers: Optional[Dict[str, str]] = None,
                query_params: Optional[Dict[str, Any]] = None,
                api_path: str = "/_matrix/client/r0") -> Awaitable[Dict]:
        """
        Make a raw HTTP request, with optional AppService timestamp massaging and external_url
        setting.

        Args:
            method: The HTTP method to use.
            path: The API endpoint to call.
                Does not include the base path (e.g. /_matrix/client/r0).
            content: The content to post as a dict (json) or bytes/str (raw).
            timestamp: The timestamp query param used for timestamp massaging.
            external_url: The external_url field to send in the content
                (only applicable if content is dict).
            headers: The dict of HTTP headers to send.
            query_params: The dict of query parameters to send.
            api_path: The base API path.

        Returns:
            The response as a dict.
        """
        query_params = query_params or {}
        if timestamp is not None:
            if isinstance(timestamp, datetime):
                timestamp = int(timestamp.replace(tzinfo=timezone.utc).timestamp() * 1000)
            query_params["ts"] = timestamp
        if isinstance(content, dict) and external_url is not None:
            content["external_url"] = external_url
        if self.identity and not self.is_real_user:
            query_params["user_id"] = self.identity

        return super(AppServiceAPI, self).request(method, path, content,
                                                  headers, query_params,
                                                  api_path)


class ChildAppServiceAPI(AppServiceAPI):
    """
    ChildAppServiceAPI is a simple way to copy AppServiceAPIs while maintaining a shared txn_id.
    """

    parent: AppServiceAPI

    def __init__(self, user: str, parent: AppServiceAPI) -> None:
        """
        Args:
            user: The Matrix user ID of the child user.
            parent: The parent AppServiceAPI instance.
        """
        super().__init__(parent.base_url, parent.bot_mxid, parent.token, user, parent.log,
                         parent.state_store, parent.session, child=True,
                         real_user_content_key=parent.real_user_content_key)
        self.parent = parent

    @property
    def txn_id(self) -> int:
        return self.parent.txn_id

    @txn_id.setter
    def txn_id(self, value: int) -> None:
        self.parent.txn_id = value
