from typing import Dict, Tuple
from abc import ABC, abstractmethod
import time

from ...client.api.types import (StateEvent, EventType, PowerLevelStateEventContent, Member,
                                 Membership, RoomID, UserID)


class StateStore(ABC):
    presence: Dict[UserID, str]
    typing: Dict[Tuple[RoomID, UserID], int]

    def __init__(self) -> None:
        # Non-persistent storage
        self.presence = {}
        self.typing = {}

    @abstractmethod
    def get_member(self, room_id: RoomID, user_id: UserID) -> Member:
        pass

    @abstractmethod
    def set_member(self, room_id: RoomID, user_id: UserID, member: Member) -> None:
        pass

    @abstractmethod
    def set_membership(self, room_id: RoomID, user_id: UserID, membership: Membership) -> None:
        pass

    @abstractmethod
    def has_power_levels(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    def get_power_levels(self, room_id: RoomID) -> PowerLevelStateEventContent:
        pass

    @abstractmethod
    def set_power_level(self, room_id: RoomID, user_id: UserID, level: int) -> None:
        pass

    @abstractmethod
    def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent) -> None:
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

    def update_state(self, evt: StateEvent) -> None:
        if evt.type == EventType.ROOM_POWER_LEVELS:
            self.set_power_levels(evt.room_id, evt.content.power_levels)
        elif evt.type == EventType.ROOM_MEMBER:
            self.set_member(evt.room_id, UserID(evt.state_key), evt.content.member)

    def get_membership(self, room_id: RoomID, user_id: UserID) -> Membership:
        return self.get_member(room_id, user_id).membership or Membership.LEAVE

    def is_joined(self, room_id: RoomID, user_id: UserID) -> bool:
        return self.get_membership(room_id, user_id) == Membership.JOIN

    def joined(self, room_id: RoomID, user_id: UserID) -> None:
        return self.set_membership(room_id, user_id, Membership.JOIN)

    def invited(self, room_id: RoomID, user_id: UserID) -> None:
        return self.set_membership(room_id, user_id, Membership.INVITE)

    def left(self, room_id: RoomID, user_id: UserID) -> None:
        return self.set_membership(room_id, user_id, Membership.LEAVE)

    def has_power_level(self, room_id: RoomID, user_id: UserID, event_type: EventType) -> bool:
        room_levels = self.get_power_levels(room_id)
        return room_levels.get_user_level(user_id) >= room_levels.get_event_level(event_type)
