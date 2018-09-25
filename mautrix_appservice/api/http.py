# -*- coding: future_fstrings -*-
from json.decoder import JSONDecodeError
from typing import Optional, Dict, Awaitable, Union, Any
from logging import Logger
import json
import asyncio

from aiohttp import ClientSession
from aiohttp.client_exceptions import ContentTypeError

from .errors import MatrixRequestError


class HTTPAPI:
    """HTTPAPI is a simple asyncio Matrix API request sender."""

    def __init__(self, base_url: str, token: str, client_session: ClientSession, txn_id: int = 0,
                 log: Optional[Logger] = None):
        """
        Args:
            base_url: The base URL of the homeserver client-server API to use.
            token: The access token to use.
            client_session: The aiohttp ClientSession to use.
            txn_id: The outgoing transaction ID to start with.
            log: The logging.Logger instance to log requests with.
        """
        self.base_url = base_url
        self.token = token
        self.log = log
        self.session = client_session
        self.validate_cert = True
        if txn_id is not None:
            self.txn_id = txn_id

    async def _send(self, method: str, endpoint: str, content: Any, query_params: Dict[str, str],
                    headers: Dict[str, str]) -> None:
        while True:
            request = self.session.request(method, endpoint, data=content,
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
                    await asyncio.sleep(response.json()["retry_after_ms"] / 1000)
                else:
                    return await response.json()

    def _log_request(self, method: str, path: str, content: Union[str, bytes],
                     query_params: Dict[str, str]) -> None:
        if not self.log:
            return
        log_content = content if not isinstance(content, bytes) else f"<{len(content)} bytes>"
        as_user = f"as user {query_params['user_id']}" if "user_id" in query_params else ""
        self.log.debug(f"{method} {path} {log_content} {as_user}".strip(" "))

    def request(self, method: str, path: str, content: Optional[Union[Dict, bytes, str]] = None,
                headers: Optional[Dict[str, str]] = None,
                query_params: Optional[Dict[str, Any]] = None,
                api_path: str = "/_matrix/client/r0") -> Awaitable[Dict]:
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
        query_params = query_params or {}
        query_params["access_token"] = self.token

        method = method.upper()
        if method not in ("GET", "PUT", "DELETE", "POST"):
            raise ValueError("Unsupported HTTP method: %s" % method)

        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        if headers.get("Content-Type", None) == "application/json":
            content = json.dumps(content)

        self._log_request(method, path, content, query_params)

        endpoint = self.base_url + api_path + path
        return self._send(method, endpoint, content, query_params, headers or {})

    def get_download_url(self, mxc_uri: str) -> str:
        """
        Get the full HTTP URL to download a mxc:// URI.
        Args:
            mxc_uri: The MXC URI whose full URL to get.
        Returns:
            The full HTTP URL.
        Raises:
            ValueError: If `mxc_uri` doesn't begin with mxc://
        """
        if mxc_uri.startswith('mxc://'):
            return f"{self.base_url}/_matrix/media/r0/download/{mxc_uri[6:]}"
        else:
            raise ValueError("MXC URI did not begin with 'mxc://'")
