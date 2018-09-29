from typing import Set, Dict
import json

from ...types import JSON
from ...client.api.types import RoomID, UserID
from .abstract import StateStore


class JSONStateStore(StateStore):
    autosave_file: str

    registrations: Set[UserID]
    members: Dict[RoomID, Dict[UserID, JSON]]
    power_levels: Dict[RoomID, JSON]

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
            "members": self.members,
            "power_levels": self.power_levels,
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

    def get_member(self, room_id: RoomID, user_id: UserID) -> JSON:
        return self.members.get(room_id, {}).get(user_id, {})

    def set_member(self, room_id: RoomID, user_id: UserID, member: JSON) -> None:
        if room_id not in self.members:
            self.members[room_id] = {}
        self.members[room_id][user_id] = member
        self._autosave()

    def set_membership(self, room_id: RoomID, user_id: UserID, membership: str) -> None:
        if room_id not in self.members:
            self.members[room_id] = {
                user_id: {
                    "membership": membership
                }
            }
        elif user_id not in self.members[room_id]:
            self.members[room_id][user_id] = {
                "membership": membership
            }
        else:
            self.members[room_id][user_id]["membership"] = membership

    def has_power_levels(self, room_id: RoomID) -> bool:
        return room_id in self.power_levels

    def get_power_levels(self, room_id: RoomID) -> JSON:
        return self.power_levels[room_id]

    def set_power_level(self, room_id: RoomID, user_id: UserID, level: int) -> None:
        if room_id not in self.power_levels:
            self.power_levels[room_id] = {
                "users": {},
                "events": {},
            }
        elif "users" not in self.power_levels[room_id]:
            self.power_levels[room_id]["users"] = {}
        self.power_levels[room_id]["users"][user_id] = level
        self._autosave()

    def set_power_levels(self, room_id: RoomID, content: JSON) -> None:
        if "events" not in content:
            content["events"] = {}
        if "users" not in content:
            content["users"] = {}
        self.power_levels[room_id] = content
        self._autosave()
