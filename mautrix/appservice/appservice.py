# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Partly based on github.com/Cadair/python-appservice-framework (MIT license)
from __future__ import annotations

from typing import Awaitable, Callable, Optional
import asyncio
import logging

from aiohttp import web
import aiohttp

from mautrix.types import JSON, RoomAlias, UserID
from mautrix.util.logging import TraceLogger

from ..api import HTTPAPI
from .api import AppServiceAPI, IntentAPI
from .as_handler import AppServiceServerMixin
from .state_store import ASStateStore, FileASStateStore

try:
    import ssl
except ImportError:
    ssl = None

QueryFunc = Callable[[web.Request], Awaitable[Optional[web.Response]]]


class AppService(AppServiceServerMixin):
    """The main AppService container."""

    server: str
    domain: str
    id: str
    verify_ssl: bool
    tls_cert: str
    tls_key: str
    as_token: str
    hs_token: str
    bot_mxid: UserID
    default_ua: str
    default_http_retry_count: int
    bridge_name: str | None
    state_store: ASStateStore

    transactions: set[str]

    query_user: Callable[[UserID], JSON]
    query_alias: Callable[[RoomAlias], JSON]
    ready: bool
    live: bool

    loop: asyncio.AbstractEventLoop
    log: TraceLogger
    app: web.Application
    runner: web.AppRunner

    def __init__(
        self,
        server: str,
        domain: str,
        as_token: str,
        hs_token: str,
        bot_localpart: str,
        id: str,
        loop: asyncio.AbstractEventLoop | None = None,
        log: logging.Logger | str | None = None,
        verify_ssl: bool = True,
        tls_cert: str | None = None,
        tls_key: str | None = None,
        query_user: QueryFunc = None,
        query_alias: QueryFunc = None,
        bridge_name: str | None = None,
        state_store: ASStateStore = None,
        aiohttp_params: dict = None,
        ephemeral_events: bool = False,
        default_ua: str = HTTPAPI.default_ua,
        default_http_retry_count: int = 0,
        connection_limit: int | None = None,
    ) -> None:
        super().__init__(ephemeral_events=ephemeral_events)
        self.server = server
        self.domain = domain
        self.id = id
        self.verify_ssl = verify_ssl
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self.connection_limit = connection_limit or 100
        self.as_token = as_token
        self.hs_token = hs_token
        self.bot_mxid = UserID(f"@{bot_localpart}:{domain}")
        self.default_ua = default_ua
        self.default_http_retry_count = default_http_retry_count
        self.bridge_name = bridge_name
        if not state_store:
            file = state_store if isinstance(state_store, str) else "mx-state.json"
            self.state_store = FileASStateStore(path=file, binary=False)
        elif isinstance(state_store, ASStateStore):
            self.state_store = state_store
        else:
            raise ValueError(f"Unsupported state store {type(state_store)}")

        self._http_session = None
        self._intent = None

        self.loop = loop or asyncio.get_event_loop()
        self.log = (
            logging.getLogger(log)
            if isinstance(log, str)
            else log or logging.getLogger("mau.appservice")
        )

        self.query_user = query_user or self.query_user
        self.query_alias = query_alias or self.query_alias
        self.live = True
        self.ready = False

        self.app = web.Application(loop=self.loop, **aiohttp_params if aiohttp_params else {})
        self.app.router.add_route("GET", "/_matrix/mau/live", self._liveness_probe)
        self.app.router.add_route("GET", "/_matrix/mau/ready", self._readiness_probe)
        self.register_routes(self.app)

        self.matrix_event_handler(self.state_store.update_state)

    @property
    def http_session(self) -> aiohttp.ClientSession:
        if self._http_session is None:
            raise AttributeError("the http_session attribute can only be used after starting")
        else:
            return self._http_session

    @property
    def intent(self) -> IntentAPI:
        if self._intent is None:
            raise AttributeError("the intent attribute can only be used after starting")
        else:
            return self._intent

    async def __aenter__(self) -> None:
        await self.start()

    async def __aexit__(self) -> None:
        await self.stop()

    async def start(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        await self.state_store.open()
        self.log.debug(f"Starting appservice web server on {host}:{port}")
        if self.server.startswith("https://") and not self.verify_ssl:
            connector = aiohttp.TCPConnector(limit=self.connection_limit, verify_ssl=False)
        else:
            connector = aiohttp.TCPConnector(limit=self.connection_limit)
        default_headers = {"User-Agent": self.default_ua}
        self._http_session = aiohttp.ClientSession(
            loop=self.loop, connector=connector, headers=default_headers
        )
        self._intent = AppServiceAPI(
            base_url=self.server,
            bot_mxid=self.bot_mxid,
            log=self.log,
            token=self.as_token,
            state_store=self.state_store,
            bridge_name=self.bridge_name,
            client_session=self._http_session,
            default_retry_count=self.default_http_retry_count,
        ).bot_intent()
        ssl_ctx = None
        if self.tls_cert and self.tls_key:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(self.tls_cert, self.tls_key)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, host, port, ssl_context=ssl_ctx)
        await site.start()

    async def stop(self) -> None:
        self.log.debug("Stopping appservice web server")
        await self.runner.cleanup()
        self._intent = None
        await self._http_session.close()
        self._http_session = None
        await self.state_store.close()

    async def _liveness_probe(self, _: web.Request) -> web.Response:
        return web.Response(status=200 if self.live else 500, text="{}")

    async def _readiness_probe(self, _: web.Request) -> web.Response:
        return web.Response(status=200 if self.ready else 500, text="{}")
