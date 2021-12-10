# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


def _pluralize(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"


def _include_if_positive(count: int, word: str) -> str:
    return f"{count} {_pluralize(count, word)}" if count > 0 else ""


def format_duration(seconds: int) -> str:
    """
    Format seconds as a simple duration in weeks/days/hours/minutes/seconds.

    Args:
        seconds: The number of seconds as an integer. Must be positive.

    Returns:
        The formatted duration.

    Examples:
        >>> from mautrix.util.format_duration import format_duration
        >>> format_duration(1234)
        '20 minutes and 34 seconds'
        >>> format_duration(987654)
        '1 week, 4 days, 10 hours, 20 minutes and 54 seconds'
        >>> format_duration(60)
        '1 minute'

    Raises:
        ValueError: if the duration is not positive.
    """
    if seconds <= 0:
        raise ValueError("format_duration only accepts positive values")
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)

    parts = [
        _include_if_positive(weeks, "week"),
        _include_if_positive(days, "day"),
        _include_if_positive(hours, "hour"),
        _include_if_positive(minutes, "minute"),
        _include_if_positive(seconds, "second"),
    ]
    parts = [part for part in parts if part]
    if len(parts) > 2:
        parts = [", ".join(parts[:-1]), parts[-1]]
    return " and ".join(parts)
