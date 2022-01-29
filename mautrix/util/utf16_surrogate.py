# From https://github.com/LonamiWebs/Telethon/blob/v1.24.0/telethon/helpers.py#L38-L62
# Copyright (c) LonamiWebs, MIT license

import struct


def add(text: str) -> str:
    """
    Add surrogate pairs to characters in the text. This makes the indices match how most platforms
    calculate string length when formatting texts using offset-based entities.

    Args:
        text: The text to add surrogate pairs to.

    Returns:
        The text with surrogate pairs.
    """
    return "".join(
        "".join(chr(y) for y in struct.unpack("<HH", x.encode("utf-16le")))
        if (0x10000 <= ord(x) <= 0x10FFFF)
        else x
        for x in text
    )


def remove(text: str) -> str:
    """
    Remove surrogate pairs from text. This does the opposite of :func:`add`.

    Args:
        text: The text with surrogate pairs.

    Returns:
        The text without surrogate pairs.
    """
    return text.encode("utf-16", "surrogatepass").decode("utf-16")


def is_within(text: str, index: int, *, length: int = None) -> bool:
    """
    Returns:
        `True` if ``index`` is within a surrogate (before and after it, not at!).
    """
    if length is None:
        length = len(text)

    return (
        1 < index < len(text)
        and "\ud800" <= text[index - 1] <= "\udfff"  # in bounds
        and "\ud800" <= text[index] <= "\udfff"  # previous is  # current is
    )


__all__ = ["add", "remove"]
