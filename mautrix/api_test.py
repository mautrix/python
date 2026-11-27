# Copyright (c) 2026 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import AsyncIterator
import asyncio

from aiohttp import web
import pytest

from .api import HTTPAPI, Method, Path
from .errors import MatrixConnectionError, MNotFound


async def _echo(req: web.Request) -> web.Response:
    return web.json_response(
        {
            "method": req.method,
            "query": dict(req.query),
            "authorization": req.headers.get("Authorization"),
            "content_type": req.headers.get("Content-Type"),
            "body": (await req.read()).decode("utf-8"),
        }
    )


async def _not_found(_: web.Request) -> web.Response:
    return web.json_response({"errcode": "M_NOT_FOUND", "error": "Nothing here"}, status=404)


async def _binary(_: web.Request) -> web.Response:
    return web.Response(body=bytes(range(256)), content_type="application/octet-stream")


async def _slow(_: web.Request) -> web.Response:
    await asyncio.sleep(2)
    return web.json_response({})


@pytest.fixture
async def server_url() -> AsyncIterator[str]:
    app = web.Application()
    app.router.add_route("*", "/_matrix/client/v3/echo", _echo)
    app.router.add_get("/_matrix/client/v3/missing", _not_found)
    app.router.add_get("/binary", _binary)
    app.router.add_get("/_matrix/client/v3/slow", _slow)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    await runner.cleanup()


async def test_json_request(server_url: str) -> None:
    api = HTTPAPI(server_url, "meow")
    resp = await api.request(Method.POST, Path.v3.echo, {"hello": "world"}, query_params={"a": 1})
    assert resp == {
        "method": "POST",
        "query": {"a": "1"},
        "authorization": "Bearer meow",
        "content_type": "application/json",
        "body": '{"hello": "world"}',
    }


async def test_error_response(server_url: str) -> None:
    api = HTTPAPI(server_url)
    with pytest.raises(MNotFound) as exc_info:
        await api.request(Method.GET, Path.v3.missing)
    assert exc_info.value.http_status == 404
    assert exc_info.value.message == "Nothing here"


async def test_raw_binary_response(server_url: str) -> None:
    api = HTTPAPI(server_url)
    status, body = await api.request_raw(Method.GET, api.base_url / "binary")
    assert status == 200
    assert body == bytes(range(256))


async def test_connection_error() -> None:
    api = HTTPAPI("http://127.0.0.1:1")
    with pytest.raises(MatrixConnectionError):
        await api.request(Method.GET, Path.v3.echo)


async def test_cancel(server_url: str) -> None:
    api = HTTPAPI(server_url)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(api.request(Method.GET, Path.v3.slow), 0.5)
    resp = await api.request(Method.GET, Path.v3.echo)
    assert resp["method"] == "GET"
