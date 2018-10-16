from typing import Optional, Dict, Awaitable, Union, List, NewType
from urllib.parse import quote as urllib_quote
from json.decoder import JSONDecodeError
from enum import Enum
from time import time
import json
import logging
import asyncio

from aiohttp import ClientSession
from aiohttp.client_exceptions import ContentTypeError

from ..errors import MatrixRequestError

JSON = NewType("JSON", Union[str, int, float, bool, None, Dict[str, 'JSON'], List['JSON']])


class APIPath(Enum):
    CLIENT = "/_matrix/client/r0"
    MEDIA = "/_matrix/media/r0"
    IDENTITY = "/_matrix/identity/r0"

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value


class Method(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value


def quote(string: str) -> str:
    return urllib_quote(string, safe="")


class PathBuilder:
    def __init__(self, path: str = "") -> None:
        self.path: str = path

    def __str__(self) -> str:
        return self.path

    def __repr__(self):
        return self.path

    def __getattr__(self, append: str) -> 'PathBuilder':
        if append is None:
            return self
        return PathBuilder(f"{self.path}/{append}")

    def raw(self, append: str) -> 'PathBuilder':
        return PathBuilder(self.path + append)

    def __getitem__(self, append: Union[str, int]) -> 'PathBuilder':
        return PathBuilder(f"{self.path}/{quote(str(append))}")


Path = PathBuilder()


class HTTPAPI:
    """HTTPAPI is a simple asyncio Matrix API request sender."""

    def __init__(self, base_url: str, token: str, client_session: ClientSession, *, txn_id: int = 0,
                 log: Optional[logging.Logger] = None, loop: Optional[asyncio.AbstractEventLoop]
                 ) -> None:
        """
        Args:
            base_url: The base URL of the homeserver client-server API to use.
            token: The access token to use.
            client_session: The aiohttp ClientSession to use.
            txn_id: The outgoing transaction ID to start with.
            log: The logging.Logger instance to log requests with.
        """
        self.base_url: str = base_url
        self.token: str = token
        self.log: Optional[logging.Logger] = log or logging.getLogger("mautrix.api")
        self.session: ClientSession = client_session
        self.loop = loop
        if txn_id is not None:
            self.txn_id: int = txn_id

    async def _send(self, method: Method, endpoint: str, content: Union[bytes, str],
                    query_params: Dict[str, str], headers: Dict[str, str]) -> JSON:
        while True:
            request = self.session.request(str(method), endpoint, data=content,
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
                    raise MatrixRequestError(code=response.status, text=await response.text(),
                                             errcode=errcode, message=message)

                if response.status == 429:
                    resp = await response.json()
                    await asyncio.sleep(resp["retry_after_ms"] / 1000, loop=self.loop)
                else:
                    return await response.json()

    def _log_request(self, method: Method, path: str, content: Union[str, bytes],
                     query_params: Dict[str, str]) -> None:
        if not self.log:
            return
        log_content = content if not isinstance(content, bytes) else f"<{len(content)} bytes>"
        as_user = f"as user {query_params['user_id']}" if "user_id" in query_params else ""
        self.log.debug(f"{method} {path} {log_content} {as_user}".strip(" "))

    def request(self, method: Method, path: str, content: Optional[Union[JSON, bytes, str]] = None,
                headers: Optional[Dict[str, str]] = None,
                query_params: Optional[Dict[str, str]] = None,
                api_path: APIPath = APIPath.CLIENT) -> Awaitable[JSON]:
        """
        Make a raw HTTP request.
        Args:
            method: The HTTP method to use.
            path: The API endpoint to call.
                Does not include the base path (e.g. /_matrix/client/r0).
            content: The content to post as a dict (json) or bytes/str (raw).
            headers: The dict of HTTP headers to send.
            query_params: The dict of query parameters to send.
            api_path: The base API path.
        Returns:
            The response as a dict.
        """
        content = content or {}
        headers = headers or {}
        headers["Authorization"] = f"Bearer {self.token}"
        query_params = query_params or {}

        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        is_json = headers.get("Content-Type", None) == "application/json"
        if is_json and isinstance(content, (dict, list)):
            content = json.dumps(content)

        self._log_request(method, path, content, query_params)

        endpoint = self.base_url + str(api_path) + str(path)
        return self._send(method, endpoint, content, query_params, headers or {})

    def get_txn_id(self) -> str:
        """Get a new unique transaction ID."""
        self.txn_id += 1
        return str(self.txn_id) + str(int(time() * 1000))

    def get_download_url(self, mxc_uri: str, download_type: str = "default") -> str:
        """
        Get the full HTTP URL to download a mxc:// URI.
        Args:
            mxc_uri: The MXC URI whose full URL to get.
            download_type: The type of download ("download" or "thumbnail")
        Returns:
            The full HTTP URL.
        Raises:
            ValueError: If `mxc_uri` doesn't begin with mxc://
        """
        if download_type == "default":
            download_type = "download"
        if mxc_uri.startswith("mxc://"):
            return f"{self.base_url}{APIPath.MEDIA.value}/{type}/{mxc_uri[6:]}"
        else:
            raise ValueError("MXC URI did not begin with `mxc://`")
