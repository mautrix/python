# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import json
import pkgutil

import aiohttp

EMOJI_VAR_URL = "https://www.unicode.org/Public/14.0.0/ucd/emoji/emoji-variation-sequences.txt"


def read_data() -> dict[str, str]:
    """
    Get the list of emoji that need a variation selector. This loads the local data file that was
    previously generated from the Unicode spec data files.

    Returns:
        A dict from hex to the emoji string (you have to bring the variation selectors yourself).
    """
    return json.loads(pkgutil.get_data("mautrix.util", "variation_selector.json"))


async def fetch_data() -> dict[str, str]:
    """
    Generate the list of emoji that need a variation selector from the Unicode spec data files.

    Returns:
        A dict from hex to the emoji string (you have to bring the variation selectors yourself).
    """
    async with aiohttp.ClientSession() as sess, sess.get(EMOJI_VAR_URL) as resp:
        data = await resp.text()
    emojis = {}
    for line in data.split("\n"):
        if "emoji style" in line:
            emoji_hex = line.split(" ", 1)[0]
            emojis[emoji_hex] = rf"\U{emoji_hex:>08}".encode("ascii").decode("unicode-escape")
    return emojis


if __name__ == "__main__":
    import asyncio
    import sys

    import pkg_resources

    path = pkg_resources.resource_filename("mautrix.util", "variation_selector.json")
    emojis = asyncio.run(fetch_data())
    with open(path, "w") as file:
        json.dump(emojis, file, indent="    ", ensure_ascii=False)
        file.write("\n")
    print(f"Wrote {len(emojis)} emojis to {path}")
    sys.exit(0)

VARIATION_SELECTOR_16 = "\ufe0f"
ADD_VARIATION_TRANSLATION = str.maketrans(
    {ord(emoji): f"{emoji}{VARIATION_SELECTOR_16}" for emoji in read_data().values()}
)
SKIN_TONE_MODIFIERS = ("\U0001F3FB", "\U0001F3FC", "\U0001F3FD", "\U0001F3FE", "\U0001F3FF")
SKIN_TONE_REPLACEMENTS = {f"{VARIATION_SELECTOR_16}{mod}": mod for mod in SKIN_TONE_MODIFIERS}
VARIATION_SELECTOR_REPLACEMENTS = {
    **SKIN_TONE_REPLACEMENTS,
    "\U0001F408\ufe0f\u200d\u2b1b\ufe0f": "\U0001F408\u200d\u2b1b",
}


def add(val: str) -> str:
    r"""
    Add emoji variation selectors (16) to all emojis that have multiple forms in the given string.
    This will remove all variation selectors first to make sure it doesn't add duplicates.

    .. versionadded:: 0.12.5

    Examples:
        >>> from mautrix.util import variation_selector
        >>> variation_selector.add("\U0001f44d")
        "\U0001f44d\ufe0f"
        >>> variation_selector.add("\U0001f44d\ufe0f")
        "\U0001f44d\ufe0f"
        >>> variation_selector.add("4\u20e3")
        "4\ufe0f\u20e3"
        >>> variation_selector.add("\U0001f9d0")
        "\U0001f9d0"

    Args:
        val: The string to add variation selectors to.

    Returns:
        The string with variation selectors added.
    """
    added = remove(val).translate(ADD_VARIATION_TRANSLATION)
    for invalid_selector, replacement in VARIATION_SELECTOR_REPLACEMENTS.items():
        added = added.replace(invalid_selector, replacement)
    return added


def remove(val: str) -> str:
    """
    Remove all emoji variation selectors in the given string.

    .. versionadded:: 0.12.5

    Args:
        val: The string to remove variation selectors from.

    Returns:
        The string with variation selectors removed.
    """
    return val.replace(VARIATION_SELECTOR_16, "")


__all__ = ["add", "remove", "read_data", "fetch_data"]
