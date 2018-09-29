from typing import Optional, Dict, Tuple
from abc import ABC, abstractmethod
import time

from ...types import JSON
from ...client.api.types import MatrixEvent, RoomID, UserID


class StateStore(ABC):
    presence: Dict[UserID, str]
    typing: Dict[Tuple[RoomID, UserID], int]

    def __init__(self) -> None:
        # Non-persistent storage
        self.presence = {}
        self.typing = {}

    @abstractmethod
    def get_member(self, room_id: RoomID, user_id: UserID) -> JSON:
        pass

    @abstractmethod
    def set_member(self, room_id: RoomID, user_id: UserID, member: JSON) -> None:
        pass

    @abstractmethod
    def set_membership(self, room_id: RoomID, user_id: UserID, membership: str) -> None:
        pass

    @abstractmethod
    def has_power_levels(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    def get_power_levels(self, room_id: RoomID) -> JSON:
        pass

    @abstractmethod
    def set_power_level(self, room_id: RoomID, user_id: UserID, level: int) -> None:
        pass

    @abstractmethod
    def set_power_levels(self, room_id: RoomID, content: JSON) -> None:
        pass

    def set_presence(self, user_id: UserID, presence: str) -> None:
        self.presence[user_id] = presence

    def has_presence(self, user_id: UserID, presence: str) -> bool:
        try:
            return self.presence[user_id] == presence
        except KeyError:
            return False

    def set_typing(self, room_id: RoomID, user_id: UserID, is_typing: bool,
                   timeout: int = 0) -> None:
        if is_typing:
            ts = int(round(time.time() * 1000))
            self.typing[(room_id, user_id)] = ts + timeout
        else:
            del self.typing[(room_id, user_id)]

    def is_typing(self, room_id: RoomID, user_id: UserID) -> bool:
        ts = int(round(time.time() * 1000))
        try:
            return self.typing[(room_id, user_id)] > ts
        except KeyError:
            return False

    def update_state(self, event: MatrixEvent) -> None:
        event_type = event["type"]
        if event_type == "m.room.power_levels":
            self.set_power_levels(event["room_id"], event["content"])
        elif event_type == "m.room.member":
            self.set_member(event["room_id"], event["state_key"], event["content"])

    def get_membership(self, room_id: RoomID, user_id: UserID) -> str:
        return self.get_member(room_id, user_id).get("membership", "left")

    def is_joined(self, room_id: RoomID, user_id: UserID) -> bool:
        return self.get_membership(room_id, user_id) == "join"

    def joined(self, room_id: RoomID, user_id: UserID) -> None:
        return self.set_membership(room_id, user_id, "join")

    def invited(self, room_id: RoomID, user_id: UserID) -> None:
        return self.set_membership(room_id, user_id, "invite")

    def left(self, room_id: RoomID, user_id: UserID) -> None:
        return self.set_membership(room_id, user_id, "left")

    def has_power_level(self, room_id: RoomID, user_id: UserID, event_id: str,
                        is_state_event: bool = False, default: Optional[int] = None) -> bool:
        room_levels = self.get_power_levels(room_id)
        default_required = default or (room_levels.get("state_default", 50) if is_state_event
                                       else room_levels.get("events_default", 0))
        required = room_levels.get("events", {}).get(event_id, default_required)
        has = room_levels.get("users", {}).get(user_id, room_levels.get("users_default", 0))
        return has >= required
