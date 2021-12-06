# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Callable, Generic, Iterable, TypeVar

T = TypeVar("T")
Number = int | float

class Metric:
    name: str
    documentation: str
    unit: str
    typ: str
    samples: list[Any]
    def add_sample(
        self,
        name: str,
        labels: Iterable[str],
        value: Any,
        timestamp: Any = None,
        exemplar: Any = None,
    ) -> None: ...

class MetricWrapperBase(Generic[T]):
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Iterable[str] = (),
        namespace: str = "",
        subsystem: str = "",
        unit: str = "",
        registry: Any = None,
        labelvalues: Any = None,
    ) -> None: ...
    def describe(self) -> list[Metric]: ...
    def collect(self) -> list[Metric]: ...
    def labels(self, *labelvalues, **labelkwargs) -> T: ...
    def remove(self, *labelvalues) -> None: ...

class ContextManager:
    def __enter__(self) -> None: ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
    def __call__(self, f) -> None: ...

class Counter(MetricWrapperBase[Counter]):
    def inc(self, amount: Number = 1) -> None: ...
    def count_exceptions(self, exception: Exception = Exception) -> ContextManager: ...

class Gauge(MetricWrapperBase[Gauge]):
    def inc(self, amount: Number = 1) -> None: ...
    def dec(self, amount: Number = 1) -> None: ...
    def set(self, value: Number = 1) -> None: ...
    def set_to_current_time(self) -> None: ...
    def track_inprogress(self) -> ContextManager: ...
    def time(self) -> ContextManager: ...
    def set_function(self, f: Callable[[], Number]) -> None: ...

class Summary(MetricWrapperBase[Summary]):
    def observe(self, amount: Number) -> None: ...
    def time(self) -> ContextManager: ...

class Histogram(MetricWrapperBase[Histogram]):
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Iterable[str] = (),
        namespace: str = "",
        subsystem: str = "",
        unit: str = "",
        registry: Any = None,
        labelvalues: Any = None,
        buckets: Iterable[Number] = (),
    ) -> None: ...
    def observe(self, amount: Number = 1) -> None: ...
    def time(self) -> ContextManager: ...

class Info(MetricWrapperBase[Info]):
    def info(self, val: dict[str, str]) -> None: ...

class Enum(MetricWrapperBase[Enum]):
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Iterable[str] = (),
        namespace: str = "",
        subsystem: str = "",
        unit: str = "",
        registry: Any = None,
        labelvalues: Any = None,
        states: Iterable[str] = None,
    ) -> None: ...
    def state(self, state: str) -> None: ...

def async_time(metric: Gauge | Summary | Histogram) -> Callable[[Callable], Callable]: ...
