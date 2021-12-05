# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import ClassVar, Mapping
from enum import Enum
from json.decoder import JSONDecodeError
from time import time
from urllib.parse import quote as urllib_quote
from urllib.parse import urljoin as urllib_join
import asyncio
import json
import logging
import platform
import sys

from aiohttp import ClientSession
from aiohttp import __version__ as aiohttp_version
from aiohttp.client_exceptions import ClientError, ContentTypeError
from yarl import URL

from mautrix import __optional_imports__
from mautrix import __version__ as mautrix_version
from mautrix.errors import MatrixConnectionError, MatrixRequestError, make_request_error
from mautrix.util.logging import TraceLogger
from mautrix.util.opt_prometheus import Counter

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

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

    CLIENT = "_matrix/client/r0"
    CLIENT_UNSTABLE = "_matrix/client/unstable"
    MEDIA = "_matrix/media/r0"
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
        >>> str(Path.rooms[room_id].event[event_id])
        "_matrix/client/r0/rooms/%21foo%3Aexample.com/event/%24bar%3Aexample.com"
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


ClientPath = PathBuilder(APIPath.CLIENT)
ClientPath.__doc__ = """
A path builder with the standard client r0 prefix ( ``/_matrix/client/r0``, :attr:`APIPath.CLIENT`)
"""
Path = PathBuilder(APIPath.CLIENT)
Path.__doc__ = """A shorter alias for :attr:`ClientPath`"""
UnstableClientPath = PathBuilder(APIPath.CLIENT_UNSTABLE)
UnstableClientPath.__doc__ = """
A path builder for client endpoints that haven't reached the spec yet
(``/_matrix/client/unstable``, :attr:`APIPath.CLIENT_UNSTABLE`)
"""
MediaPath = PathBuilder(APIPath.MEDIA)
MediaPath.__doc__ = """
A path builder for standard media r0 paths (``/_matrix/media/r0``, :attr:`APIPath.MEDIA`)

Examples:
    >>> from mautrix.api import MediaPath
    >>> str(MediaPath.config)
    "_matrix/media/r0/config"
"""
SynapseAdminPath = PathBuilder(APIPath.SYNAPSE_ADMIN)
SynapseAdminPath.__doc__ = """
A path builder for synapse-specific admin API paths
(``/_synapse/admin/v1``, :attr:`APIPath.SYNAPSE_ADMIN`)

Examples:
    >>> from mautrix.api import SynapseAdminPath
    >>> user_id = "@user:example.com"
    >>> str(SynapseAdminPath.users[user_id]/login)
    "_synapse/admin/v1/users/%40user%3Aexample.com/login"
"""

_req_id = 0


def _next_global_req_id() -> int:
    global _req_id
    _req_id += 1
    return _req_id


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
        content: bytes | str,
        query_params: dict[str, str],
        headers: dict[str, str],
    ) -> JSON:
        request = self.session.request(
            str(method), url, data=content, params=query_params, headers=headers
        )
        async with request as response:
            if response.status < 200 or response.status >= 300:
                errcode = message = None
                try:
                    response_data = await response.json()
                    errcode = response_data["errcode"]
                    message = response_data["error"]
                except (JSONDecodeError, ContentTypeError, KeyError):
                    pass
                raise make_request_error(
                    http_status=response.status,
                    text=await response.text(),
                    errcode=errcode,
                    message=message,
                )
            return await response.json()

    def _log_request(
        self,
        method: Method,
        path: PathBuilder,
        content: str | bytes,
        orig_content,
        query_params: dict[str, str],
        req_id: int,
    ) -> None:
        if not self.log:
            return
        log_content = content if not isinstance(content, bytes) else f"<{len(content)} bytes>"
        as_user = query_params.get("user_id", None)
        level = 1 if path == Path.sync else 5
        self.log.log(
            level,
            f"{method}#{req_id} /{path} {log_content}".strip(" "),
            extra={
                "matrix_http_request": {
                    "req_id": req_id,
                    "method": str(method),
                    "path": str(path),
                    "content": (
                        orig_content if isinstance(orig_content, (dict, list)) else log_content
                    ),
                    "user": as_user,
                }
            },
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
        content: dict | list | bytes | str | None = None,
        headers: dict[str, str] | None = None,
        query_params: Mapping[str, str] | None = None,
        retry_count: int | None = None,
        metrics_method: str = "",
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
        backoff = 4
        while True:
            self._log_request(method, path, content, orig_content, query_params, req_id)
            API_CALLS.labels(method=metrics_method).inc()
            try:
                return await self._send(method, full_url, content, query_params, headers or {})
            except MatrixRequestError as e:
                API_CALLS_FAILED.labels(method=metrics_method).inc()
                if retry_count > 0 and e.http_status in (502, 503, 504):
                    self.log.warning(
                        f"Request #{req_id} failed with HTTP {e.http_status}, "
                        f"retrying in {backoff} seconds"
                    )
                else:
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
        return f"mautrix-python_R{self.txn_id}@T{int(time() * 1000)}"

    def get_download_url(
        self, mxc_uri: str, download_type: Literal["download", "thumbnail"] = "download"
    ) -> URL:
        """
        Get the full HTTP URL to download a ``mxc://`` URI.

        Args:
            mxc_uri: The MXC URI whose full URL to get.
            download_type: The type of download ("download" or "thumbnail").

        Returns:
            The full HTTP URL.

        Raises:
            ValueError: If `mxc_uri` doesn't begin with ``mxc://``.

        Examples:
            >>> api = HTTPAPI(...)
            >>> api.get_download_url("mxc://matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6")
            "https://matrix.org/_matrix/media/r0/download/matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6"
        """
        if mxc_uri.startswith("mxc://"):
            return self.base_url / str(APIPath.MEDIA) / download_type / mxc_uri[6:]
        else:
            raise ValueError("MXC URI did not begin with `mxc://`")
