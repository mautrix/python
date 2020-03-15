# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Partly based on github.com/Cadair/python-appservice-framework (MIT license)
from typing import Optional, Callable, Awaitable, Union, Set, Dict
from aiohttp import web
import aiohttp
import asyncio
import logging

from ..api import JSON
from ..types import UserID, RoomAlias, Event
from .api import AppServiceAPI, IntentAPI
from .state_store import StateStore, JSONStateStore
from .as_handler import AppServiceServerMixin

QueryFunc = Callable[[web.Request], Awaitable[Optional[web.Response]]]


class AppService(AppServiceServerMixin):
    """The main AppService container."""

    server: str
    domain: str
    verify_ssl: bool
    as_token: str
    hs_token: str
    bot_mxid: UserID
    real_user_content_key: str
    state_store: StateStore

    transactions: Set[str]

    query_user: Callable[[UserID], JSON]
    query_alias: Callable[[RoomAlias], JSON]
    ready: bool
    live: bool

    loop: asyncio.AbstractEventLoop
    log: logging.Logger
    app: web.Application
    runner: web.AppRunner

    def __init__(self, server: str, domain: str, as_token: str, hs_token: str, bot_localpart: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None,
                 log: Optional[Union[logging.Logger, str]] = None, verify_ssl: bool = True,
                 query_user: QueryFunc = None, query_alias: QueryFunc = None,
                 real_user_content_key: Optional[str] = "net.maunium.appservice.puppet",
                 state_store: StateStore = None, aiohttp_params: Dict = None) -> None:
        super().__init__()
        self.server = server
        self.domain = domain
        self.verify_ssl = verify_ssl
        self.as_token = as_token
        self.hs_token = hs_token
        self.bot_mxid = UserID(f"@{bot_localpart}:{domain}")
        self.real_user_content_key: str = real_user_content_key
        if isinstance(state_store, StateStore):
            self.state_store = state_store
        else:
            file = state_store if isinstance(state_store, str) else "mx-state.json"
            self.state_store: JSONStateStore = JSONStateStore(autosave_file=file)
            self.state_store.load(file)

        self._http_session = None
        self._intent = None

        self.loop = loop or asyncio.get_event_loop()
        self.log = (logging.getLogger(log) if isinstance(log, str)
                    else log or logging.getLogger("mautrix_appservice"))

        self.query_user = query_user or self.query_user
        self.query_alias = query_alias or self.query_alias
        self.live = True
        self.ready = False

        self.app = web.Application(loop=self.loop, **aiohttp_params if aiohttp_params else {})
        self.app.router.add_route("GET", "/_matrix/mau/live", self._liveness_probe)
        self.app.router.add_route("GET", "/_matrix/mau/ready", self._readiness_probe)
        self.register_routes(self.app)

        async def update_state(event: Event):
            self.state_store.update_state(event)

        self.matrix_event_handler(update_state)

    @property
    def http_session(self) -> aiohttp.ClientSession:
        if self._http_session is None:
            raise AttributeError("the http_session attribute can only be used after starting")
        else:
            return self._http_session

    @property
    def intent(self) -> 'IntentAPI':
        if self._intent is None:
            raise AttributeError("the intent attribute can only be used after starting")
        else:
            return self._intent

    async def __aenter__(self) -> None:
        await self.start()

    async def __aexit__(self) -> None:
        await self.stop()

    async def start(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        connector = None
        self.log.debug(f"Starting appservice web server on {host}:{port}")
        if self.server.startswith("https://") and not self.verify_ssl:
            connector = aiohttp.TCPConnector(verify_ssl=False)
        self._http_session = aiohttp.ClientSession(loop=self.loop, connector=connector)
        self._intent = AppServiceAPI(base_url=self.server, bot_mxid=self.bot_mxid, log=self.log,
                                     token=self.as_token, state_store=self.state_store,
                                     real_user_content_key=self.real_user_content_key,
                                     client_session=self._http_session).bot_intent()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, host, port)
        await site.start()

    async def stop(self) -> None:
        self.log.debug("Stopping appservice web server")
        await self.runner.cleanup()
        self._intent = None
        await self._http_session.close()
        self._http_session = None

    async def _liveness_probe(self, _: web.Request) -> web.Response:
        return web.Response(status=200 if self.live else 500, text="{}")

    async def _readiness_probe(self, _: web.Request) -> web.Response:
        return web.Response(status=200 if self.ready else 500, text="{}")
