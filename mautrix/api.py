# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, Union, TYPE_CHECKING
from urllib.parse import quote as urllib_quote, urljoin as urllib_join
from json.decoder import JSONDecodeError
from enum import Enum
from time import time
import json
import logging
import asyncio

from yarl import URL
from aiohttp import ClientSession
from aiohttp.client_exceptions import ContentTypeError, ClientError

from mautrix.errors import make_request_error, MatrixConnectionError
from mautrix.util.logging import TraceLogger

if TYPE_CHECKING:
    from mautrix.types import JSON


class APIPath(Enum):
    """
    The known Matrix API path prefixes.
    These don't start with a slash so they can be used nicely with yarl.
    """
    CLIENT = "_matrix/client/r0"
    CLIENT_UNSTABLE = "_matrix/client/unstable"
    MEDIA = "_matrix/media/r0"

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

    def __init__(self, path: Union[str, APIPath] = "") -> None:
        self.path: str = str(path)

    def __str__(self) -> str:
        return self.path

    def __repr__(self):
        return self.path

    def __getattr__(self, append: str) -> 'PathBuilder':
        if append is None:
            return self
        return PathBuilder(f"{self.path}/{append}")

    def raw(self, append: str) -> 'PathBuilder':
        """
        Directly append a string to the path.

        Args:
            append: The string to append.
        """
        if append is None:
            return self
        return PathBuilder(self.path + append)

    def __eq__(self, other: Union['PathBuilder', str]) -> bool:
        return other.path == self.path if isinstance(other, PathBuilder) else other == self.path

    @staticmethod
    def _quote(string: str) -> str:
        return urllib_quote(string, safe="")

    def __getitem__(self, append: Union[str, int]) -> 'PathBuilder':
        if append is None:
            return self
        return PathBuilder(f"{self.path}/{self._quote(str(append))}")


Path = PathBuilder(APIPath.CLIENT)
ClientPath = Path
UnstableClientPath = PathBuilder(APIPath.CLIENT_UNSTABLE)
MediaPath = PathBuilder(APIPath.MEDIA)


class HTTPAPI:
    """HTTPAPI is a simple asyncio Matrix API request sender."""

    base_url: URL
    token: str
    log: TraceLogger
    loop: asyncio.AbstractEventLoop
    session: ClientSession
    txn_id: Optional[int]

    def __init__(self, base_url: Union[URL, str], token: str = "", *,
                 client_session: ClientSession = None,
                 txn_id: int = 0, log: Optional[TraceLogger] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """
        Args:
            base_url: The base URL of the homeserver client-server API to use.
            token: The access token to use.
            client_session: The aiohttp ClientSession to use.
            txn_id: The outgoing transaction ID to start with.
            log: The logging.Logger instance to log requests with.
        """
        self.base_url = URL(base_url)
        self.token = token
        self.log = log or logging.getLogger("mau.http")
        self.loop = loop or asyncio.get_event_loop()
        self.session = client_session or ClientSession(loop=self.loop)
        if txn_id is not None:
            self.txn_id = txn_id

    async def _send(self, method: Method, url: URL, content: Union[bytes, str],
                    query_params: Dict[str, str], headers: Dict[str, str]) -> 'JSON':
        while True:
            request = self.session.request(str(method), url, data=content,
                                           params=query_params, headers=headers)
            async with request as response:
                if response.status < 200 or response.status >= 300:
                    errcode = message = None
                    try:
                        response_data = await response.json()
                        errcode = response_data["errcode"]
                        message = response_data["error"]
                    except (JSONDecodeError, ContentTypeError, KeyError):
                        pass
                    raise make_request_error(http_status=response.status,
                                             text=await response.text(),
                                             errcode=errcode, message=message)

                if response.status == 429:
                    resp = await response.json()
                    seconds = resp["retry_after_ms"] / 1000
                    self.log.debug(f"Request to {url} returned 429, "
                                   f"waiting {seconds} seconds and retrying")
                    await asyncio.sleep(seconds, loop=self.loop)
                else:
                    return await response.json()

    def _log_request(self, method: Method, path: PathBuilder, content: Union[str, bytes],
                     orig_content, query_params: Dict[str, str]) -> None:
        if not self.log:
            return
        log_content = content if not isinstance(content, bytes) else f"<{len(content)} bytes>"
        as_user = query_params.get("user_id", None)
        level = 1 if path == Path.sync else 5
        self.log.log(level, f"{method} /{path} {log_content}".strip(" "),
                     extra={"matrix_http_request": {
                         "method": str(method),
                         "path": str(path),
                         "content": (orig_content if isinstance(orig_content, (dict, list))
                                     else log_content),
                         "user": as_user,
                     }})

    def _full_path(self, path: Union[PathBuilder, str]) -> str:
        path = str(path)
        if path and path[0] == "/":
            path = path[1:]
        base_path = self.base_url.raw_path
        if base_path[-1] != "/":
            base_path += "/"
        return urllib_join(base_path, path)

    async def request(self, method: Method, path: Union[PathBuilder, str],
                      content: Optional[Union[dict, list, bytes, str]] = None,
                      headers: Optional[Dict[str, str]] = None,
                      query_params: Optional[Dict[str, str]] = None) -> 'JSON':
        """
        Make a raw Matrix API request.

        Args:
            method: The HTTP method to use.
            path: The full API endpoint to call (including the _matrix/... prefix)
            content: The content to post as a dict/list (will be serialized as JSON)
                or bytes/str (will be sent as-is).
            headers: A dict of HTTP headers to send.
                If the headers don't contain ``Content-Type``, it'll be set to ``application/json``.
                The ``Authorization`` header is always overridden if :attr:`token` is set.
            query_params: A dict of query parameters to send.

        Returns:
            The parsed response JSON.
        """
        content = content or {}
        headers = headers or {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        query_params = query_params or {}

        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        is_json = headers.get("Content-Type", None) == "application/json"
        orig_content = content
        if is_json and isinstance(content, (dict, list)):
            content = json.dumps(content)

        self._log_request(method, path, content, orig_content, query_params)
        full_url = self.base_url.with_path(self._full_path(path), encoded=True)

        try:
            return await self._send(method, full_url, content, query_params, headers or {})
        except ClientError as e:
            raise MatrixConnectionError(str(e)) from e

    def get_txn_id(self) -> str:
        """Get a new unique transaction ID."""
        self.txn_id += 1
        return f"mautrix-python_R{self.txn_id}@T{int(time() * 1000)}"

    def get_download_url(self, mxc_uri: str, download_type: str = "download") -> URL:
        """
        Get the full HTTP URL to download a mxc:// URI.

        Args:
            mxc_uri: The MXC URI whose full URL to get.
            download_type: The type of download ("download" or "thumbnail")

        Returns:
            The full HTTP URL.

        Raises:
            ValueError: If `mxc_uri` doesn't begin with mxc://

        Examples:
            >>> api = HTTPAPI(...)
            >>> api.get_download_url("mxc://matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6")
            "https://matrix.org/_matrix/media/r0/download/matrix.org/pqjkOuKZ1ZKRULWXgz2IVZV6"
        """
        if mxc_uri.startswith("mxc://"):
            return self.base_url / str(APIPath.MEDIA) / download_type / mxc_uri[6:]
        else:
            raise ValueError("MXC URI did not begin with `mxc://`")
