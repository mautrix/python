# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Set, Dict
import pickle

from ...types import PowerLevelStateEventContent, Member, Membership, RoomID, UserID
from .abstract import StateStore


class PickleStateStore(StateStore):
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
            output = open(file, "wb")
        else:
            output = file

        pickle.dump({
            "registrations": self.registrations,
            "members": self.members,
            "power_levels": self.power_levels,
        }, output)

        if isinstance(file, str):
            output.close()

    def load(self, file: str) -> None:
        if isinstance(file, str):
            try:
                input_source = open(file, "rb")
            except FileNotFoundError:
                return
        else:
            input_source = file

        data = pickle.load(input_source)
        if "registrations" in data:
            self.registrations = set(data["registrations"])
        if "members" in data:
            self.members = data["members"]
        if "power_levels" in data:
            self.power_levels = data["power_levels"]

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
