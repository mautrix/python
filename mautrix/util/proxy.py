from __future__ import annotations

from typing import Awaitable, Callable, TypeVar
import asyncio
import json
import logging
import time
import urllib.request

from aiohttp import ClientConnectionError
from yarl import URL

from mautrix.util.logging import TraceLogger

try:
    from aiohttp_socks import ProxyConnectionError, ProxyError, ProxyTimeoutError
except ImportError:

    class ProxyError(Exception):
        pass

    ProxyConnectionError = ProxyTimeoutError = ProxyError

RETRYABLE_PROXY_EXCEPTIONS = (
    ProxyError,
    ProxyTimeoutError,
    ProxyConnectionError,
    ClientConnectionError,
    ConnectionError,
    asyncio.TimeoutError,
)


class ProxyHandler:
    current_proxy_url: str | None = None
    log = logging.getLogger("mau.proxy")

    def __init__(self, api_url: str | None) -> None:
        self.api_url = api_url

    def get_proxy_url_from_api(self, reason: str | None = None) -> str | None:
        assert self.api_url is not None

        api_url = str(URL(self.api_url).update_query({"reason": reason} if reason else {}))

        # NOTE: using urllib.request to intentionally block the whole bridge until the proxy change applied
        request = urllib.request.Request(api_url, method="GET")
        self.log.debug("Requesting proxy from: %s", api_url)

        try:
            with urllib.request.urlopen(request) as f:
                response = json.loads(f.read().decode())
        except Exception:
            self.log.exception("Failed to retrieve proxy from API")
            return self.current_proxy_url
        else:
            return response["proxy_url"]

    def update_proxy_url(self, reason: str | None = None) -> bool:
        old_proxy = self.current_proxy_url
        new_proxy = None

        if self.api_url is not None:
            new_proxy = self.get_proxy_url_from_api(reason)
        else:
            new_proxy = urllib.request.getproxies().get("http")

        if old_proxy != new_proxy:
            self.log.debug("Set new proxy URL: %s", new_proxy)
            self.current_proxy_url = new_proxy
            return True

        self.log.debug("Got same proxy URL: %s", new_proxy)
        return False

    def get_proxy_url(self) -> str | None:
        if not self.current_proxy_url:
            self.update_proxy_url()

        return self.current_proxy_url


T = TypeVar("T")


async def proxy_with_retry(
    name: str,
    func: Callable[[], Awaitable[T]],
    logger: TraceLogger,
    proxy_handler: ProxyHandler,
    on_proxy_change: Callable[[], Awaitable[None]],
    max_retries: int = 10,
    min_wait_seconds: int = 0,
    max_wait_seconds: int = 60,
    multiply_wait_seconds: int = 10,
    retryable_exceptions: tuple[Exception] = RETRYABLE_PROXY_EXCEPTIONS,
    reset_after_seconds: int | None = None,
) -> T:
    errors = 0
    last_error = 0

    while True:
        try:
            return await func()
        except retryable_exceptions as e:
            errors += 1
            if errors > max_retries:
                raise
            wait = errors * multiply_wait_seconds
            wait = max(wait, min_wait_seconds)
            wait = min(wait, max_wait_seconds)
            logger.warning(
                "%s while trying to %s, retrying in %d seconds",
                e.__class__.__name__,
                name,
                wait,
            )
            if errors > 1 and proxy_handler.update_proxy_url(
                f"{e.__class__.__name__} while trying to {name}"
            ):
                await on_proxy_change()

            # If sufficient time has passed since the previous error, reset the
            # error count. Useful for long running tasks with rare failures.
            if reset_after_seconds is not None:
                now = time.time()
                if last_error and now - last_error > reset_after_seconds:
                    errors = 0
                last_error = now
