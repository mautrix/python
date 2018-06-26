# -*- coding: future_fstrings -*-
from typing import Optional
from abc import ABC, abstractmethod
import json
import time


class StateStore(ABC):
    def __init__(self):
        # Non-persistent storage
        self.presence = {}
        self.typing = {}

    @abstractmethod
    def get_member(self, room: str, user: str) -> dict:
        pass

    @abstractmethod
    def set_member(self, room: str, user: str, member: dict):
        pass

    @abstractmethod
    def set_membership(self, room: str, user: str, membership: str):
        pass

    @abstractmethod
    def has_power_levels(self, room: str) -> bool:
        pass

    @abstractmethod
    def get_power_levels(self, room: str) -> dict:
        pass

    @abstractmethod
    def set_power_level(self, room: str, user: str, level: int):
        pass

    @abstractmethod
    def set_power_levels(self, room: str, content: dict):
        pass

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

    def update_state(self, event: dict):
        event_type = event["type"]
        if event_type == "m.room.power_levels":
            self.set_power_levels(event["room_id"], event["content"])
        elif event_type == "m.room.member":
            self.set_member(event["room_id"], event["state_key"], event["content"])

    def get_membership(self, room: str, user: str) -> str:
        return self.get_member(room, user).get("membership", "left")

    def is_joined(self, room: str, user: str) -> bool:
        return self.get_membership(room, user) == "join"

    def joined(self, room: str, user: str):
        return self.set_membership(room, user, "join")

    def invited(self, room: str, user: str):
        return self.set_membership(room, user, "invite")

    def left(self, room: str, user: str):
        return self.set_membership(room, user, "left")

    def has_power_level(self, room: str, user: str, event: str, is_state_event: bool = False,
                        default: Optional[int] = None) -> bool:
        room_levels = self.get_power_levels(room)
        default_required = default or (room_levels.get("state_default", 50) if is_state_event
                                       else room_levels.get("events_default", 0))
        required = room_levels.get("events", {}).get(event, default_required)
        has = room_levels.get("users", {}).get(user, room_levels.get("users_default", 0))
        return has >= required


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
