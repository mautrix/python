# -*- coding: future_fstrings -*-
from typing import Optional
from abc import ABC, abstractmethod
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
