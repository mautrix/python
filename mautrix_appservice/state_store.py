# -*- coding: future_fstrings -*-
# matrix-appservice-python - A Matrix Application Service framework written in Python.
# Copyright (C) 2018 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from typing import Optional
import json
import time


class StateStore:
    def __init__(self, autosave_file: str = None):
        self.autosave_file = autosave_file

        # Persistent storage
        self.registrations = set()
        self.memberships = {}
        self.power_levels = {}

        # Non-persistent storage
        self.presence = {}
        self.typing = {}

    def save(self, file: str):
        if isinstance(file, str):
            output = open(file, "w")
        else:
            output = file

        json.dump({
            "registrations": list(self.registrations),
            "memberships": self.memberships,
            "power_levels": self.power_levels,
        }, output)

        if isinstance(file, str):
            output.close()

    def load(self, file: str):
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
        if "memberships" in data:
            self.memberships = data["memberships"]
        if "power_levels" in data:
            self.power_levels = data["power_levels"]

        if isinstance(file, str):
            input_source.close()

    def _autosave(self):
        if self.autosave_file:
            self.save(self.autosave_file)

    def set_presence(self, user: str, presence: str):
        self.presence[user] = presence

    def has_presence(self, user: str, presence: str) -> bool:
        try:
            return self.presence[user] == presence
        except KeyError:
            return False

    def set_typing(self, room_id: str, user: str, is_typing: bool, timeout: int = 0):
        if is_typing:
            ts = int(round(time.time() * 1000))
            self.typing[(room_id, user)] = ts + timeout
        else:
            del self.typing[(room_id, user)]

    def is_typing(self, room_id: str, user: str) -> bool:
        ts = int(round(time.time() * 1000))
        try:
            return self.typing[(room_id, user)] > ts
        except KeyError:
            return False

    def is_registered(self, user: str) -> bool:
        return user in self.registrations

    def registered(self, user: str):
        self.registrations.add(user)
        self._autosave()

    def get_membership(self, room: str, user: str) -> str:
        return self.memberships.get(room, {}).get(user, "left")

    def is_joined(self, room: str, user: str) -> bool:
        return self.get_membership(room, user) == "join"

    def set_membership(self, room: str, user: str, membership: str):
        if room not in self.memberships:
            self.memberships[room] = {}
        self.memberships[room][user] = membership
        self._autosave()

    def joined(self, room: str, user: str):
        return self.set_membership(room, user, "join")

    def invited(self, room: str, user: str):
        return self.set_membership(room, user, "invite")

    def left(self, room: str, user: str):
        return self.set_membership(room, user, "left")

    def has_power_levels(self, room: str) -> bool:
        return room in self.power_levels

    def get_power_levels(self, room: str) -> dict:
        return self.power_levels[room]

    def has_power_level(self, room: str, user: str, event: str, is_state_event: bool = False,
                        default: Optional[int] = None) -> bool:
        room_levels = self.power_levels.get(room, {})
        default_required = default or (room_levels.get("state_default", 50) if is_state_event
                                       else room_levels.get("events_default", 0))
        required = room_levels.get("events", {}).get(event, default_required)
        has = room_levels.get("users", {}).get(user, room_levels.get("users_default", 0))
        return has >= required

    def set_power_level(self, room: str, user: str, level: int):
        if room not in self.power_levels:
            self.power_levels[room] = {
                "users": {},
                "events": {},
            }
        elif "users" not in self.power_levels[room]:
            self.power_levels[room]["users"] = {}
        self.power_levels[room]["users"][user] = level
        self._autosave()

    def set_power_levels(self, room: str, content: dict):
        if "events" not in content:
            content["events"] = {}
        if "users" not in content:
            content["users"] = {}
        self.power_levels[room] = content
        self._autosave()
