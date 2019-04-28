# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Set, Dict
import json

from ...types import PowerLevelStateEventContent, Member, Membership, RoomID, UserID
from .abstract import StateStore


class JSONStateStore(StateStore):
    autosave_file: str

    registrations: Set[UserID]
    members: Dict[RoomID, Dict[UserID, Member]]
    power_levels: Dict[RoomID, PowerLevelStateEventContent]

    def __init__(self, autosave_file: str = None) -> None:
        super().__init__()
        self.autosave_file = autosave_file

        self.registrations = set()
        self.members = {}
        self.power_levels = {}

    def save(self, file: str) -> None:
        if isinstance(file, str):
            output = open(file, "w")
        else:
            output = file

        json.dump({
            "registrations": list(self.registrations),
            "members": {room_id: {user_id: member.serialize()}
                        for room_id, members in self.members.items()
                        for user_id, member in members.items()},
            "power_levels": {room_id: levels.serialize()
                             for room_id, levels in self.power_levels.items()},
        }, output)

        if isinstance(file, str):
            output.close()

    def load(self, file: str) -> None:
        if isinstance(file, str):
            try:
                input_source = open(file, "r")
            except FileNotFoundError:
                return
        else:
            input_source = file

        data = json.load(input_source)
        if "registrations" in data:
            self.registrations = set(data["registrations"])
        if "members" in data:
            self.members = {room_id: {user_id: Member.deserialize(content)}
                            for room_id, members in data["members"].items()
                            for user_id, content in members.items()}
        if "power_levels" in data:
            self.power_levels = {room_id: PowerLevelStateEventContent.deserialize(content)
                                 for room_id, content in data["power_levels"].items()}

        if isinstance(file, str):
            input_source.close()

    def _autosave(self) -> None:
        if self.autosave_file:
            self.save(self.autosave_file)

    def is_registered(self, user_id: UserID) -> bool:
        return user_id in self.registrations

    def registered(self, user_id: UserID) -> None:
        self.registrations.add(user_id)
        self._autosave()

    def get_member(self, room_id: RoomID, user_id: UserID) -> Member:
        return self.members.get(room_id, {}).get(user_id, Member())

    def set_member(self, room_id: RoomID, user_id: UserID, member: Member) -> None:
        if room_id not in self.members:
            self.members[room_id] = {}
        self.members[room_id][user_id] = member
        self._autosave()

    def set_membership(self, room_id: RoomID, user_id: UserID, membership: Membership) -> None:
        self.members.setdefault(room_id, {}).setdefault(user_id, Member()).membership = membership

    def has_power_levels(self, room_id: RoomID) -> bool:
        return room_id in self.power_levels

    def get_power_levels(self, room_id: RoomID) -> PowerLevelStateEventContent:
        return self.power_levels[room_id]

    def set_power_level(self, room_id: RoomID, user_id: UserID, level: int) -> None:
        try:
            self.power_levels[room_id].set_user_level(user_id, level)
        except KeyError:
            self.power_levels[room_id] = PowerLevelStateEventContent()
            self.power_levels[room_id].set_user_level(user_id, level)
        self._autosave()

    def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent) -> None:
        self.power_levels[room_id] = content
        self._autosave()
