# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import re

# Generated with curl https://cdn.jsdelivr.net/npm/emojibase-data@7.0.0/en/data.json | jq -c '[.[] | select(.emoji | endswith("\ufe0f")) | select(.emoji | length == 2) | .hexcode]'

# fmt: off
# don't split this into 342 lines please
EMOJIS_WITH_VARIATION_HEX = [
    "263A", "1F610", "2639", "2620", "1F47D", "2763", "2764", "1F573", "1F4A3", "1F5E8", "1F5EF",
    "1F590", "270C", "1F448", "1F449", "1F446", "1F447", "261D", "1F44D", "1F44E", "270D", "1F442",
    "1F441", "1F575", "1F574", "26F7", "1F3C2", "1F3CC", "1F3C4", "1F3CA", "26F9", "1F3CB",
    "1F46A", "1F5E3", "1F415", "1F408", "1F43F", "1F426", "1F54A", "1F41F", "1F577", "1F578",
    "1F3F5", "2618", "1F336", "2615", "1F378", "1F37D", "1F30D", "1F30E", "1F30F", "1F5FA",
    "1F3D4", "26F0", "1F3D5", "1F3D6", "1F3DC", "1F3DD", "1F3DE", "1F3DF", "1F3DB", "1F3D7",
    "1F3D8", "1F3DA", "1F3E0", "1F3ED", "26EA", "26E9", "26F2", "26FA", "1F3D9", "2668", "1F687",
    "1F68D", "1F691", "1F694", "1F698", "1F3CE", "1F3CD", "1F6B2", "1F6E3", "1F6E4", "1F6E2",
    "26FD", "2693", "26F5", "1F6F3", "26F4", "1F6E5", "2708", "1F6E9", "1F6F0", "1F6CE", "231B",
    "23F3", "231A", "23F1", "23F2", "1F570", "1F55B", "1F567", "1F550", "1F55C", "1F551", "1F55D",
    "1F552", "1F55E", "1F553", "1F55F", "1F554", "1F560", "1F555", "1F561", "1F556", "1F562",
    "1F557", "1F563", "1F558", "1F564", "1F559", "1F565", "1F55A", "1F566", "1F315", "1F31C",
    "1F321", "2600", "2B50", "2601", "26C5", "26C8", "1F324", "1F325", "1F326", "1F327", "1F328",
    "1F329", "1F32A", "1F32B", "1F32C", "2602", "2614", "26F1", "26A1", "2744", "2603", "26C4",
    "2604", "1F397", "1F39F", "1F396", "1F3C6", "26BD", "26BE", "26F3", "26F8", "1F3AE", "1F579",
    "2660", "2665", "2666", "2663", "265F", "1F004", "1F3AD", "1F5BC", "1F453", "1F576", "1F6CD",
    "1F393", "26D1", "1F508", "1F399", "1F39A", "1F39B", "1F3A7", "1F4FB", "260E", "1F4DF",
    "1F4BB", "1F5A5", "1F5A8", "2328", "1F5B1", "1F5B2", "1F4BF", "1F39E", "1F4FD", "1F3AC",
    "1F4FA", "1F4F7", "1F4F9", "1F50D", "1F56F", "1F4DA", "1F5DE", "1F3F7", "1F4B0", "1F4B3",
    "2709", "1F4E4", "1F4E5", "1F4E6", "1F4EB", "1F4EA", "1F4EC", "1F4ED", "1F5F3", "270F", "2712",
    "1F58B", "1F58A", "1F58C", "1F58D", "1F5C2", "1F5D2", "1F5D3", "1F4CB", "1F587", "2702",
    "1F5C3", "1F5C4", "1F5D1", "1F512", "1F513", "1F5DD", "26CF", "2692", "1F6E0", "1F5E1", "2694",
    "1F6E1", "2699", "1F5DC", "2696", "26D3", "2697", "1F6CF", "1F6CB", "26B0", "26B1", "267F",
    "1F6B9", "1F6BA", "1F6BC", "26A0", "26D4", "1F6AD", "2622", "2623", "2B06", "2197", "27A1",
    "2198", "2B07", "2199", "2B05", "2196", "2195", "2194", "21A9", "21AA", "2934", "2935", "269B",
    "1F549", "2721", "2638", "262F", "271D", "2626", "262A", "262E", "2648", "2649", "264A",
    "264B", "264C", "264D", "264E", "264F", "2650", "2651", "2652", "2653", "25B6", "23E9", "23ED",
    "23EF", "25C0", "23EA", "23EE", "23F8", "23F9", "23FA", "23CF", "2640", "2642", "26A7", "2716",
    "267E", "203C", "2049", "2753", "2757", "3030", "2695", "267B", "269C", "2B55", "2611", "2714",
    "303D", "2733", "2734", "2747", "00A9", "00AE", "2122", "1F170", "1F171", "2139", "24C2",
    "1F17E", "1F17F", "1F202", "1F237", "1F22F", "1F21A", "3297", "3299", "26AB", "26AA", "2B1B",
    "2B1C", "25FC", "25FB", "25FE", "25FD", "25AA", "25AB", "1F3F3",
]
# fmt: on

EMOJIS_WITH_VARIATION = (
    (rf"\u{emoji}" if len(emoji) == 4 else rf"\U{emoji:>08}")
    .encode("ascii")
    .decode("unicode-escape")
    for emoji in EMOJIS_WITH_VARIATION_HEX
)

VARIATION_SELECTOR_16 = "\ufe0f"

KEYCAP = "\u20e3"
KEYCAP_REGEX = re.compile(fr"([0-9*#])\u20e3")
KEYCAP_REGEX_REPLACEMENT = fr"\1{VARIATION_SELECTOR_16}{KEYCAP}"

ADD_VARIATION_TRANSLATION = str.maketrans(
    {ord(emoji): f"{emoji}{VARIATION_SELECTOR_16}" for emoji in EMOJIS_WITH_VARIATION}
)


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
        "\U0001f44D\ufe0f"
        >>> variation_selector.add("\U0001f9d0")
        "\U0001f9d0"

    Args:
        val: The string to add variation selectors to.

    Returns:
        The string with variation selectors added.
    """
    val = remove(val)
    val = val.translate(ADD_VARIATION_TRANSLATION)
    val = KEYCAP_REGEX.sub(KEYCAP_REGEX_REPLACEMENT, val)
    return val


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


__all__ = ["add", "remove"]
