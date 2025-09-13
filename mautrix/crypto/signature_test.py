# Copyright (c) 2025 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from mautrix.types import SigningKey, UserID

from .signature import verify_signature_json


def test_verify_signature_json() -> None:
    assert verify_signature_json(
        # This is actually a federation PDU rather than a device signature,
        # but they're both 25519 curves so it doesn't make a difference.
        {
            "auth_events": [
                "$L8Ak6A939llTRIsZrytMlLDXQhI4uLEjx-wb1zSg-Bw",
                "$QJmr7mmGeXGD4Tof0ZYSPW2oRGklseyHTKtZXnF-YNM",
                "$7bkKK_Z-cGQ6Ae4HXWGBwXyZi3YjC6rIcQzGfVyl3Eo",
            ],
            "content": {},
            "depth": 3212,
            "hashes": {"sha256": "K549YdTnv62Jn84Y7sS5ZN3+AdmhleZHbenbhUpR2R8"},
            "origin_server_ts": 1754242687127,
            "prev_events": ["$DAhJg4jVsqk5FRatE2hbT1dSA8D2ASy5DbjEHIMSHwY"],
            "room_id": "!offtopic-2:continuwuity.org",
            "sender": "@tulir:maunium.net",
            "type": "m.room.message",
            "signatures": {
                UserID("maunium.net"): {
                    "ed25519:a_xxeS": "SkzZdZ+rH22kzCBBIAErTdB0Vg6vkFmzvwjlOarGul72EnufgtE/tJcd3a8szAdK7f1ZovRyQxDgVm/Ib2u0Aw"
                }
            },
            "unsigned": {"age_ts": 1754242687146},
        },
        UserID("maunium.net"),
        "a_xxeS",
        SigningKey("lVt/CC3tv74OH6xTph2JrUmeRj/j+1q0HVa0Xf4QlCg"),
    )
