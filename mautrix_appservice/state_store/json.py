# -*- coding: future_fstrings -*-
import json

from .abstract import StateStore


class JSONStateStore(StateStore):
    def __init__(self, autosave_file: str = None):
        super().__init__()
        self.autosave_file = autosave_file

        self.registrations = set()
        self.members = {}
        self.power_levels = {}

    def save(self, file: str):
        if isinstance(file, str):
            output = open(file, "w")
        else:
            output = file

        json.dump({
            "registrations": list(self.registrations),
            "members": self.members,
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
        if "members" in data:
            self.members = data["members"]
        if "power_levels" in data:
            self.power_levels = data["power_levels"]

        if isinstance(file, str):
            input_source.close()

    def _autosave(self):
        if self.autosave_file:
            self.save(self.autosave_file)

    def is_registered(self, user: str) -> bool:
        return user in self.registrations

    def registered(self, user: str):
        self.registrations.add(user)
        self._autosave()

    def get_member(self, room: str, user: str) -> dict:
        return self.members.get(room, {}).get(user, {})

    def set_member(self, room: str, user: str, member: dict):
        if room not in self.members:
            self.members[room] = {}
        self.members[room][user] = member
        self._autosave()

    def set_membership(self, room: str, user: str, membership: str):
        if room not in self.members:
            self.members[room] = {
                user: {
                    "membership": membership
                }
            }
        elif user not in self.members[room]:
            self.members[room][user] = {
                "membership": membership
            }
        else:
            self.members[room][user]["membership"] = membership

    def has_power_levels(self, room: str) -> bool:
        return room in self.power_levels

    def get_power_levels(self, room: str) -> dict:
        return self.power_levels[room]

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
