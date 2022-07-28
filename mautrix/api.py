# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import AsyncGenerator, ClassVar, Literal, Mapping, Union
from enum import Enum
from json.decoder import JSONDecodeError
from urllib.parse import quote as urllib_quote, urljoin as urllib_join
import asyncio
import inspect
import json
import logging
import platform
import time

from aiohttp import ClientResponse, ClientSession, __version__ as aiohttp_version
from aiohttp.client_exceptions import ClientError, ContentTypeError
from yarl import URL

from mautrix import __optional_imports__, __version__ as mautrix_version
from mautrix.errors import MatrixConnectionError, MatrixRequestError, make_request_error
from mautrix.util.logging import TraceLogger
from mautrix.util.opt_prometheus import Counter

if __optional_imports__:
    # Safe to import, but it's not actually needed, so don't force-import the whole types module.
    from mautrix.types import JSON

API_CALLS = Counter(
    name="bridge_matrix_api_calls",
    documentation="The number of Matrix client API calls made",
    labelnames=("method",),
)
API_CALLS_FAILED = Counter(
    name="bridge_matrix_api_calls_failed",
    documentation="The number of Matrix client API calls which failed",
    labelnames=("method",),
)


class APIPath(Enum):
    """
    The known Matrix API path prefixes.
    These don't start with a slash so they can be used nicely with yarl.
    """

    CLIENT = "_matrix/client"
    MEDIA = "_matrix/media"
    SYNAPSE_ADMIN = "_synapse/admin"

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value


class Method(Enum):
    """A HTTP method."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value


class PathBuilder:
    """
    A utility class to build API paths.

    Examples:
        >>> from mautrix.api import Path
        >>> room_id = "!foo:example.com"
        >>> event_id = "$bar:example.com"
        >>> str(Path.v3.rooms[room_id].event[event_id])
        "_matrix/client/v3/rooms/%21foo%3Aexample.com/event/%24bar%3Aexample.com"
    """

    def __init__(self, path: str | APIPath = "") -> None:
        self.path: str = str(path)

    def __str__(self) -> str:
        return self.path

    def __repr__(self):
        return self.path

    def __getattr__(self, append: str) -> PathBuilder:
        if append is None:
            return self
        return PathBuilder(f"{self.path}/{append}")

    def raw(self, append: str) -> PathBuilder:
        """
        Directly append a string to the path.

        Args:
            append: The string to append.
        """
        if append is None:
            return self
        return PathBuilder(self.path + append)

    def __eq__(self, other: PathBuilder | str) -> bool:
        return other.path == self.path if isinstance(other, PathBuilder) else other == self.path

    @staticmethod
    def _quote(string: str) -> str:
        return urllib_quote(string, safe="")

    def __getitem__(self, append: str | int) -> PathBuilder:
        if append is None:
            return self
        return PathBuilder(f"{self.path}/{self._quote(str(append))}")

    def replace(self, find: str, replace: str) -> PathBuilder:
        return PathBuilder(self.path.replace(find, replace))


ClientPath = PathBuilder(APIPath.CLIENT)
ClientPath.__doc__ = """
A path builder with the standard client prefix ( ``/_matrix/client``, :attr:`APIPath.CLIENT`).
"""
Path = PathBuilder(APIPath.CLIENT)
Path.__doc__ = """A shorter alias for :attr:`ClientPath`"""
MediaPath = PathBuilder(APIPath.MEDIA)
MediaPath.__doc__ = """
A path builder with the standard media prefix (``/_matrix/media``, :attr:`APIPath.MEDIA`)

Examples:
    >>> from mautrix.api import MediaPath
    >>> str(MediaPath.v3.config)
    "_matrix/media/v3/config"
"""
SynapseAdminPath = PathBuilder(APIPath.SYNAPSE_ADMIN)
SynapseAdminPath.__doc__ = """
A path builder for synapse-specific admin API paths
(``/_synapse/admin``, :attr:`APIPath.SYNAPSE_ADMIN`)

Examples:
    >>> from mautrix.api import SynapseAdminPath
    >>> user_id = "@user:example.com"
    >>> str(SynapseAdminPath.v1.users[user_id]/login)
    "_synapse/admin/v1/users/%40user%3Aexample.com/login"
"""

_req_id = 0
AsyncBody = AsyncGenerator[Union[bytes, bytearray, memoryview], None]


def _next_global_req_id() -> int:
    global _req_id
    _req_id += 1
    return _req_id


async def _async_iter_bytes(data: bytearray | bytes, chunk_size: int = 1024**2) -> AsyncBody:
    with memoryview(data) as mv:
        for i in range(0, len(data), chunk_size):
            yield mv[i : i + chunk_size]


class HTTPAPI:
    """HTTPAPI is a simple asyncio Matrix API request sender."""

    default_ua: ClassVar[str] = (
        f"mautrix-python/{mautrix_version} aiohttp/{aiohttp_version} "
        f"Python/{platform.python_version()}"
    )
    """
    The default value for the ``User-Agent`` header.

    You should prepend your program name and version here before creating any HTTPAPI instances
    in order to have proper user agents for all requests.
    """
    global_default_retry_count: ClassVar[int] = 0
    """The default retry count to use if an instance-specific value is not passed."""

    base_url: URL
    """The base URL of the homeserver's client-server API to use."""
    token: str
    """The access token to use in requests."""
    log: TraceLogger
    """The :class:`logging.Logger` instance to log requests with."""
    session: ClientSession
    """The aiohttp ClientSession instance to make requests with."""
    txn_id: int | None
    """A counter used for generating transaction IDs."""
    default_retry_count: int
    """The default retry count to use if a custom value is not passed to :meth:`request`"""

    def __init__(
        self,
        base_url: URL | str,
        token: str = "",
        *,
        client_session: ClientSession = None,
        default_retry_count: int = None,
        txn_id: int = 0,
        log: TraceLogger | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """
        Args:
            base_url: The base URL of the homeserver's client-server API to use.
            token: The access token to use.
            client_session: The aiohttp client session to use.
            txn_id: The outgoing transaction ID to start with.
            log: The :class:`logging.Logger` instance to log requests with.
            default_retry_count: Default number of retries to do when encountering network errors.
        """
        self.base_url = URL(base_url)
        self.token = token
        self.log = log or logging.getLogger("mau.http")
        self.session = client_session or ClientSession(
            loop=loop, headers={"User-Agent": self.default_ua}
        )
        if txn_id is not None:
            self.txn_id = txn_id
        if default_retry_count is not None:
            self.default_retry_count = default_retry_count
        else:
            self.default_retry_count = self.global_default_retry_count

    async def _send(
        self,
        method: Method,
        url: URL,
        content: bytes | bytearray | str | AsyncBody,
        query_params: dict[str, str],
        headers: dict[str, str],
    ) -> tuple[JSON, ClientResponse]:
        request = self.session.request(
            str(method), url, data=content, params=query_params, headers=headers
        )
        async with request as response:
            if response.status < 200 or response.status >= 300:
                errcode = unstable_errcode = message = None
                try:
                    response_data = await response.json()
                    errcode = response_data["errcode"]
                    message = response_data["error"]
                    unstable_errcode = response_data.get("org.matrix.msc3848.unstable.errcode")
                except (JSONDecodeError, ContentTypeError, KeyError):
                    pass
                raise make_request_error(
                    http_status=response.status,
                    text=await response.text(),
                    errcode=errcode,
                    message=message,
                    unstable_errcode=unstable_errcode,
                )
            return await response.json(), response

    def _log_request(
        self,
        method: Method,
        url: URL,
        content: str | bytes | bytearray | AsyncBody,
        orig_content,
        query_params: dict[str, str],
        headers: dict[str, str],
        req_id: int,
        sensitive: bool,
    ) -> None:
        if not self.log:
            return
        if isinstance(content, (bytes, bytearray)):
            log_content = f"<{len(content)} bytes>"
        elif inspect.isasyncgen(content):
            size = headers.get("Content-Length", None)
            log_content = f"<{size} async bytes>" if size else f"<stream with unknown length>"
        elif sensitive:
            log_content = f"<{len(content)} sensitive bytes>"
        else:
            log_content = content
        as_user = query_params.get("user_id", None)
        level = 5 if url.path.endswith("/v3/sync") else 10
        self.log.log(
            level,
            f"req #{req_id}: {method} {url} {log_content}".strip(" "),
            extra={
                "matrix_http_request": {
                    "req_id": req_id,
                    "method": str(method),
                    "url": str(url),
                    "content": (
                        orig_content
                        if isinstance(orig_content, (dict, list)) and not sensitive
                        else log_content
                    ),
                    "user": as_user,
                }
            },
        )

    def _log_request_done(
        self, path: PathBuilder, req_id: int, duration: float, status: int
    ) -> None:
        level = 5 if path == Path.v3.sync else 10
        duration_str = f"{duration * 1000:.1f}ms" if duration < 1 else f"{duration:.3f}s"
        path_without_prefix = f"/{path}".replace("/_matrix/client", "")
        self.log.log(
            level,
            f"req #{req_id} ({path_without_prefix}) completed in {duration_str} "
            f"with status {status}",
        )

    def _full_path(self, path: PathBuilder | str) -> str:
        path = str(path)
        if path and path[0] == "/":
            path = path[1:]
        base_path = self.base_url.raw_path
        if base_path[-1] != "/":
            base_path += "/"
        return urllib_join(base_path, path)

    async def request(
        self,
        method: Method,
        path: PathBuilder | str,
        content: dict | list | bytes | bytearray | str | AsyncBody | None = None,
        headers: dict[str, str] | None = None,
        query_params: Mapping[str, str] | None = None,
        retry_count: int | None = None,
        metrics_method: str = "",
        min_iter_size: int = 25 * 1024 * 1024,
        sensitive: bool = False,
    ) -> JSON:
        """
        Make a raw Matrix API request.

        Args:
            method: The HTTP method to use.
            path: The full API endpoint to call (including the _matrix/... prefix)
            content: The content to post as a dict/list (will be serialized as JSON)
                     or bytes/str (will be sent as-is).
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
            sensitive: If True, the request content will not be logged.

        Returns:
            The parsed response JSON.
        """
        headers = headers or {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        query_params = query_params or {}
        if isinstance(query_params, dict):
            query_params = {k: v for k, v in query_params.items() if v is not None}

        if method != Method.GET:
            content = content or {}
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
            orig_content = content
            is_json = headers.get("Content-Type", None) == "application/json"
            if is_json and isinstance(content, (dict, list)):
                content = json.dumps(content)
        else:
            orig_content = content = None
        full_url = self.base_url.with_path(self._full_path(path), encoded=True)
        req_id = _next_global_req_id()

        if retry_count is None:
            retry_count = self.default_retry_count
        if inspect.isasyncgen(content):
            # Can't retry with non-static body
            retry_count = 0
        do_fake_iter = content and hasattr(content, "__len__") and len(content) > min_iter_size
        if do_fake_iter:
            headers["Content-Length"] = str(len(content))
        backoff = 4
        log_url = full_url.with_query(query_params)
        while True:
            self._log_request(
                method, log_url, content, orig_content, query_params, headers, req_id, sensitive
            )
            API_CALLS.labels(method=metrics_method).inc()
            req_content = _async_iter_bytes(content) if do_fake_iter else content
            start = time.monotonic()
            try:
                resp_data, resp = await self._send(
                    method, full_url, req_content, query_params, headers or {}
                )
                self._log_request_done(path, req_id, time.monotonic() - start, resp.status)
                return resp_data
            except MatrixRequestError as e:
                API_CALLS_FAILED.labels(method=metrics_method).inc()
                if retry_count > 0 and e.http_status in (502, 503, 504):
                    self.log.warning(
                        f"Request #{req_id} failed with HTTP {e.http_status}, "
                        f"retrying in {backoff} seconds"
                    )
                else:
                    self._log_request_done(path, req_id, time.monotonic() - start, e.http_status)
                    raise
            except ClientError as e:
                API_CALLS_FAILED.labels(method=metrics_method).inc()
                if retry_count > 0:
                    self.log.warning(
                        f"Request #{req_id} failed with {e}, retrying in {backoff} seconds"
                    )
                else:
                    raise MatrixConnectionError(str(e)) from e
            except Exception:
                API_CALLS_FAILED.labels(method=metrics_method).inc()
                raise
            await asyncio.sleep(backoff)
            backoff *= 2
            retry_count -= 1

    def get_txn_id(self) -> str:
        """Get a new unique transaction ID."""
        self.txn_id += 1
        return f"mautrix-python_{time.time_ns()}_{self.txn_id}"

    def get_download_url(
        self,
        mxc_uri: str,
        download_type: Literal["download", "thumbnail"] = "download",
        file_name: str | None = None,
    ) -> URL:
        """
        Get the full HTTP URL to download a ``mxc://`` URI.

        Args:
            mxc_uri: The MXC URI whose full URL to get.
            download_type: The type of download ("download" or "thumbnail").
            file_name: Optionally, a file name to include in the download URL.

        Returns:
            The full HTTP URL.

        Raises:
            ValueError: If `mxc_uri` doesn't begin with ``mxc://``.

        Examples:
            >>> api = HTTPAPI(base_url="https://matrix-client.matrix.org", ...)
            >>> api.get_download_url("mxc://matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6")
            "https://matrix-client.matrix.org/_matrix/media/v3/download/matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6"
            >>> api.get_download_url("mxc://matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6", file_name="hello.png")
            "https://matrix-client.matrix.org/_matrix/media/v3/download/matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6/hello.png"
        """
        server_name, media_id = self.parse_mxc_uri(mxc_uri)
        url = self.base_url / str(APIPath.MEDIA) / "v3" / download_type / server_name / media_id
        if file_name:
            url /= file_name
        return url

    @staticmethod
    def parse_mxc_uri(mxc_uri: str) -> tuple[str, str]:
        """
        Parse a ``mxc://`` URI.

        Args:
            mxc_uri: The MXC URI to parse.

        Returns:
            A tuple containing the server and media ID of the MXC URI.

        Raises:
            ValueError: If `mxc_uri` doesn't begin with ``mxc://``.
        """
        if mxc_uri.startswith("mxc://"):
            server_name, media_id = mxc_uri[6:].split("/")
            return server_name, media_id
        else:
            raise ValueError("MXC URI did not begin with `mxc://`")
