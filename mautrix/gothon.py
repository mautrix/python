# Copyright (c) 2026 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Bindings for libgothon, the mautrix-go based shared library that makes all Matrix HTTP requests
and handles end-to-end encryption.

Calls are started with :meth:`Runtime.call` and run in goroutines. When a call finishes, the
library queues the result and writes to a pipe, which the event loop watches with ``add_reader``.
Log lines from Go are delivered through the same queue and passed to the :mod:`logging` module.
"""

from __future__ import annotations

from typing import Any
from pathlib import Path
import asyncio
import ctypes
import itertools
import json
import logging
import os

from mautrix.errors import MatrixConnectionError, make_request_error

LIBRARY_PATH = Path(__file__).with_name("libgothon.so")

_log_levels = {
    "trace": 5,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
    "panic": logging.CRITICAL,
}


class GoError(Exception):
    """An error returned by libgothon that doesn't have a more specific exception class."""

    def __init__(self, type: str, message: str) -> None:
        super().__init__(message)
        self.type = type


class _Result(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint64),
        ("data", ctypes.c_void_p),
        ("data_len", ctypes.c_size_t),
        ("body", ctypes.c_void_p),
        ("body_len", ctypes.c_size_t),
    ]


def log_params(log: logging.Logger) -> dict[str, Any]:
    """Get the parameters that make Go send its log lines to the given logger."""
    return {"name": log.name, "level": log.getEffectiveLevel()}


def _make_error(error: dict[str, Any]) -> Exception:
    if error["type"] == "http":
        return make_request_error(
            http_status=error["status"],
            text=error.get("text", ""),
            errcode=error.get("errcode"),
            message=error.get("message"),
            unstable_errcode=error.get("unstable_errcode"),
        )
    elif error["type"] == "connection":
        return MatrixConnectionError(error["message"])
    return GoError(error["type"], error["message"])


def _unwrap(payload: dict[str, Any]) -> Any:
    if "error" in payload:
        raise _make_error(payload["error"])
    return payload.get("result")


def _log_from_go(payload: dict[str, Any]) -> None:
    log = logging.getLogger(payload.pop("logger", "mau.gothon"))
    level = _log_levels.get(payload.pop("level", ""), logging.INFO)
    if not log.isEnabledFor(level):
        return
    message = payload.pop("message", "")
    fields = " ".join(
        f"{key}={value if isinstance(value, str) else json.dumps(value)}"
        for key, value in payload.items()
    )
    log.log(level, f"{message} {fields}" if fields else message)


class Runtime:
    """A loaded libgothon instance."""

    def __init__(self, path: Path = LIBRARY_PATH) -> None:
        if not path.exists():
            raise RuntimeError(
                f"{path} not found. "
                "Build it with `go build -buildmode=c-shared -o ../mautrix/libgothon.so` "
                "in the gothon directory, or reinstall mautrix."
            )
        lib = ctypes.CDLL(str(path))
        lib.gothon_init.restype = ctypes.c_int
        lib.gothon_call.argtypes = [
            ctypes.c_uint64,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        lib.gothon_call_sync.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(_Result),
        ]
        lib.gothon_cancel.argtypes = [ctypes.c_uint64]
        lib.gothon_poll.argtypes = [ctypes.POINTER(_Result)]
        lib.gothon_poll.restype = ctypes.c_int
        lib.gothon_free.argtypes = [ctypes.c_void_p]
        self._lib = lib
        self._fd = lib.gothon_init()
        if self._fd < 0:
            raise RuntimeError("Failed to initialize libgothon")
        os.set_blocking(self._fd, False)
        self._call_ids = itertools.count(1)
        self._calls: dict[int, asyncio.Future[tuple[dict[str, Any], bytes]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def call_sync(self, method: str, params: dict[str, Any]) -> Any:
        """Run a call that doesn't do any I/O and return its result."""
        data = json.dumps(params).encode("utf-8")
        result = _Result()
        self._lib.gothon_call_sync(method.encode("utf-8"), data, len(data), ctypes.byref(result))
        payload, _ = self._take(result)
        return _unwrap(payload)

    async def call(
        self, method: str, params: dict[str, Any], body: bytes = b""
    ) -> tuple[Any, bytes]:
        """Run a call in a goroutine and return its result and response body."""
        self._attach_loop()
        call_id = next(self._call_ids)
        future = self._loop.create_future()
        self._calls[call_id] = future
        data = json.dumps(params).encode("utf-8")
        self._lib.gothon_call(call_id, method.encode("utf-8"), data, len(data), body, len(body))
        try:
            payload, resp_body = await future
        except asyncio.CancelledError:
            self._calls.pop(call_id, None)
            self._lib.gothon_cancel(call_id)
            raise
        return _unwrap(payload), resp_body

    def _attach_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if loop is self._loop:
            return
        if self._loop is not None and not self._loop.is_closed():
            self._loop.remove_reader(self._fd)
        loop.add_reader(self._fd, self._drain)
        self._loop = loop

    def _take(self, result: _Result) -> tuple[dict[str, Any], bytes]:
        data = body = b""
        if result.data:
            data = ctypes.string_at(result.data, result.data_len)
            self._lib.gothon_free(result.data)
        if result.body:
            body = ctypes.string_at(result.body, result.body_len)
            self._lib.gothon_free(result.body)
        return json.loads(data), body

    def _drain(self) -> None:
        try:
            os.read(self._fd, 4096)
        except BlockingIOError:
            pass
        result = _Result()
        while self._lib.gothon_poll(ctypes.byref(result)):
            payload, body = self._take(result)
            if result.id == 0:
                _log_from_go(payload)
                continue
            future = self._calls.pop(result.id, None)
            if future is not None and not future.done() and not future.get_loop().is_closed():
                future.set_result((payload, body))


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    """Get the shared libgothon instance, loading it on first use."""
    global _runtime
    if _runtime is None:
        _runtime = Runtime()
    return _runtime
