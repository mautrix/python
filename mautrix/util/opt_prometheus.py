# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Callable, Awaitable, Any, Union


class _NoopPrometheusEntity:
    """NoopPrometheusEntity is a class that can be used as a no-op placeholder for prometheus
    metrics objects when prometheus_client isn't installed."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        if not kwargs and len(args) == 1 and callable(args[0]):
            return args[0]
        return self

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __getattr__(self, item):
        return self


try:
    from prometheus_client import Counter, Gauge, Summary, Histogram, Info, Enum

    is_installed = True
except ImportError:
    Counter = Gauge = Summary = Histogram = Info = Enum = _NoopPrometheusEntity
    is_installed = False


def async_time(metric):
    if not hasattr(metric, "time") or not callable(metric.time):
        raise ValueError("async_time only supports metrics that support timing")

    def decorator(fn):
        async def wrapper(*args, **kwargs):
            with metric.time():
                return await fn(*args, **kwargs)

        return wrapper if is_installed else fn

    return decorator


__all__ = ["Counter", "Gauge", "Summary", "Histogram", "Info", "Enum", "async_time", "is_installed"]
