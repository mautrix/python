# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest

from .format_duration import format_duration

tests = {
    1234: "20 minutes and 34 seconds",
    987654: "1 week, 4 days, 10 hours, 20 minutes and 54 seconds",
    694861: "1 week, 1 day, 1 hour, 1 minute and 1 second",
    1: "1 second",
    59: "59 seconds",
    60: "1 minute",
    120: "2 minutes",
}


def test_format_duration() -> None:
    for seconds, formatted in tests.items():
        assert format_duration(seconds) == formatted


def test_non_positive_error() -> None:
    with pytest.raises(ValueError):
        format_duration(0)

    with pytest.raises(ValueError):
        format_duration(-123)
