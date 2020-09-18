# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, Any, Tuple, TypeVar, Generic, Union, Callable, Dict

T = TypeVar('T')


class Metric:
    name: str
    documentation: str
    unit: str
    typ: str
    samples: List[Any]

    def add_sample(self, name: str, labels: List[str], value: Any, timestamp: Any = None,
                   exemplar: Any = None) -> None: ...


class MetricWrapperBase(Generic[T]):
    def __init__(self, name: str, documentation: str, labelnames: Tuple[str, ...] = (),
                 namespace: str = "", subsystem: str = "", unit: str = "", registry: Any = None,
                 labelvalues: Any = None) -> None: ...

    def describe(self) -> List[Metric]: ...

    def collect(self) -> List[Metric]: ...

    def labels(self, *labelvalues, **labelkwargs) -> T: ...

    def remove(self, *labelvalues) -> None: ...


class ContextManager:
    def __enter__(self) -> None: ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...

    def __call__(self, f) -> None: ...


class Counter(MetricWrapperBase['Counter']):
    def inc(self, amount: int = 1) -> None: ...

    def count_exceptions(self, exception: Exception = Exception) -> ContextManager: ...


class Gauge(MetricWrapperBase['Gauge']):
    def inc(self, amount: Union[int, float] = 1) -> None: ...

    def dec(self, amount: Union[int, float] = 1) -> None: ...

    def set(self, value: Union[int, float] = 1) -> None: ...

    def set_to_current_time(self) -> None: ...

    def track_inprogress(self) -> ContextManager: ...

    def time(self) -> ContextManager: ...

    def set_function(self, f: Callable[[], float]) -> None: ...


class Summary(MetricWrapperBase['Summary']):
    def observe(self, amount: Union[int, float]) -> None: ...

    def time(self) -> ContextManager: ...


class Histogram(MetricWrapperBase['Histogram']):
    def __init__(self, name: str, documentation: str, labelnames: Tuple[str, ...] = (),
                 namespace: str = "", subsystem: str = "", unit: str = "", registry: Any = None,
                 labelvalues: Any = None, buckets: Tuple[float, ...] = ()) -> None: ...

    def observe(self, amount: Union[int, float] = 1) -> None: ...

    def time(self) -> ContextManager: ...


class Info(MetricWrapperBase['Info']):
    def info(self, val: Dict[str, str]) -> None: ...


class Enum(MetricWrapperBase['Enum']):
    def __init__(self, name: str, documentation: str, labelnames: Tuple[str, ...] = (),
                 namespace: str = "", subsystem: str = "", unit: str = "", registry: Any = None,
                 labelvalues: Any = None, states: List[str] = None) -> None: ...

    def state(self, state: str) -> None: ...
