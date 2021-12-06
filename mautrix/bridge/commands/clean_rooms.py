# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import List, NamedTuple, Optional, Union

from mautrix.appservice import IntentAPI
from mautrix.errors import MatrixRequestError
from mautrix.types import EventID, EventType, RoomID, UserID

from ... import bridge as br
from .handler import SECTION_ADMIN, CommandEvent, command_handler


class ManagementRoom(NamedTuple):
    room_id: RoomID
    user_id: UserID


class RoomSearchResults(NamedTuple):
    management_rooms: List[ManagementRoom]
    unidentified_rooms: List[RoomID]
    tombstoned_rooms: List[RoomID]
    portals: List[br.BasePortal]
    empty_portals: List[br.BasePortal]


async def _find_rooms(bridge: br.Bridge, intent: Optional[IntentAPI] = None) -> RoomSearchResults:
    results = RoomSearchResults([], [], [], [], [])
    intent = intent or bridge.az.intent
    rooms = await intent.get_joined_rooms()
    for room_id in rooms:
        portal = await bridge.get_portal(room_id)
        if not portal:
            try:
                tombstone = await intent.get_state_event(room_id, EventType.ROOM_TOMBSTONE)
                if tombstone and tombstone.replacement_room:
                    results.tombstoned_rooms.append(room_id)
                    continue
            except MatrixRequestError:
                pass
            try:
                members = await intent.get_room_members(room_id)
            except MatrixRequestError:
                members = []
            if len(members) == 2:
                other_member = members[0] if members[0] != intent.mxid else members[1]
                if bridge.is_bridge_ghost(other_member):
                    results.unidentified_rooms.append(room_id)
                else:
                    results.management_rooms.append(ManagementRoom(room_id, other_member))
            else:
                results.unidentified_rooms.append(room_id)
        else:
            members = await portal.get_authenticated_matrix_users()
            if len(members) == 0:
                results.empty_portals.append(portal)
            else:
                results.portals.append(portal)

    return results


@command_handler(
    needs_admin=True,
    needs_auth=False,
    management_only=True,
    name="clean-rooms",
    help_section=SECTION_ADMIN,
    help_text="Clean up unused portal/management rooms.",
)
async def clean_rooms(evt: CommandEvent) -> EventID:
    results = await _find_rooms(evt.bridge)

    reply = ["#### Management rooms (M)"]
    reply += [
        f"{n + 1}. [M{n + 1}](https://matrix.to/#/{room}) (with {other_member}"
        for n, (room, other_member) in enumerate(results.management_rooms)
    ] or ["No management rooms found."]
    reply.append("#### Active portal rooms (A)")
    reply += [
        f"{n + 1}. [A{n + 1}](https://matrix.to/#/{portal.mxid}) "
        f'(to remote chat "{portal.name}")'
        for n, portal in enumerate(results.portals)
    ] or ["No active portal rooms found."]
    reply.append("#### Unidentified rooms (U)")
    reply += [
        f"{n + 1}. [U{n + 1}](https://matrix.to/#/{room})"
        for n, room in enumerate(results.unidentified_rooms)
    ] or ["No unidentified rooms found."]
    reply.append("#### Tombstoned rooms (T)")
    reply += [
        f"{n + 1}. [T{n + 1}](https://matrix.to/#/{room})"
        for n, room in enumerate(results.tombstoned_rooms)
    ] or ["No tombstoned rooms found."]
    reply.append("#### Inactive portal rooms (I)")
    reply += [
        f"{n}. [I{n}](https://matrix.to/#/{portal.mxid}) " f'(to remote chat "{portal.name}")'
        for n, portal in enumerate(results.empty_portals)
    ] or ["No inactive portal rooms found."]

    reply += [
        "#### Usage",
        (
            "To clean the recommended set of rooms (unidentified & inactive portals), "
            "type `$cmdprefix+sp clean-recommended`"
        ),
        "",
        (
            "To clean other groups of rooms, type `$cmdprefix+sp clean-groups <letters>` "
            "where `letters` are the first letters of the group names (M, A, U, I, T)"
        ),
        "",
        (
            "To clean specific rooms, type `$cmdprefix+sp clean-range <range>` "
            "where `range` is the range (e.g. `5-21`) prefixed with the first letter of"
            "the group name. (e.g. `I2-6`)"
        ),
        "",
        (
            "Please note that you will have to re-run `$cmdprefix+sp clean-rooms` "
            "between each use of the commands above."
        ),
    ]

    evt.sender.command_status = {
        "next": lambda clean_evt: set_rooms_to_clean(clean_evt, results),
        "action": "Room cleaning",
    }

    return await evt.reply("\n".join(reply))


async def set_rooms_to_clean(evt, results: RoomSearchResults) -> None:
    command = evt.args[0]
    rooms_to_clean: List[Union[br.BasePortal, RoomID]] = []
    if command == "clean-recommended":
        rooms_to_clean += results.empty_portals
        rooms_to_clean += results.unidentified_rooms
    elif command == "clean-groups":
        if len(evt.args) < 2:
            return await evt.reply("**Usage:** $cmdprefix+sp clean-groups [M][A][U][I]")
        groups_to_clean = evt.args[1].upper()
        if "M" in groups_to_clean:
            rooms_to_clean += [room_id for (room_id, user_id) in results.management_rooms]
        if "A" in groups_to_clean:
            rooms_to_clean += results.portals
        if "U" in groups_to_clean:
            rooms_to_clean += results.unidentified_rooms
        if "I" in groups_to_clean:
            rooms_to_clean += results.empty_portals
        if "T" in groups_to_clean:
            rooms_to_clean += results.tombstoned_rooms
    elif command == "clean-range":
        try:
            clean_range = evt.args[1]
            group, clean_range = clean_range[0], clean_range[1:]
            start, end = clean_range.split("-")
            start, end = int(start), int(end)
            if group == "M":
                group = [room_id for (room_id, user_id) in results.management_rooms]
            elif group == "A":
                group = results.portals
            elif group == "U":
                group = results.unidentified_rooms
            elif group == "I":
                group = results.empty_portals
            elif group == "T":
                group = results.tombstoned_rooms
            else:
                raise ValueError("Unknown group")
            rooms_to_clean = group[start - 1 : end]
        except (KeyError, ValueError):
            return await evt.reply("**Usage:** $cmdprefix+sp clean-range <_M|A|U|I_><range>")
    else:
        return await evt.reply(
            f"Unknown room cleaning action `{command}`. "
            "Use `$cmdprefix+sp cancel` to cancel room cleaning."
        )

    evt.sender.command_status = {
        "next": lambda confirm: execute_room_cleanup(confirm, rooms_to_clean),
        "action": "Room cleaning",
    }
    await evt.reply(
        f"To confirm cleaning up {len(rooms_to_clean)} rooms, type `$cmdprefix+sp confirm-clean`."
    )


async def execute_room_cleanup(evt, rooms_to_clean: List[Union[br.BasePortal, RoomID]]) -> None:
    if len(evt.args) > 0 and evt.args[0] == "confirm-clean":
        await evt.reply(f"Cleaning {len(rooms_to_clean)} rooms. This might take a while.")
        cleaned = 0
        for room in rooms_to_clean:
            if isinstance(room, br.BasePortal):
                await room.cleanup_and_delete()
                cleaned += 1
            else:
                await br.BasePortal.cleanup_room(evt.az.intent, room, "Room deleted")
                cleaned += 1
        evt.sender.command_status = None
        await evt.reply(f"{cleaned} rooms cleaned up successfully.")
    else:
        await evt.reply("Room cleaning cancelled.")
