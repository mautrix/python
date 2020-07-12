# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, Awaitable, Optional, List, Dict
from abc import ABC, abstractmethod

from mautrix.types import (StateEvent, EventType, RoomID, UserID, PowerLevelStateEventContent,
                           MemberStateEventContent, RoomEncryptionStateEventContent, Member,
                           Membership)


class StateStore(ABC):
    async def open(self) -> None:
        pass

    async def close(self) -> None:
        await self.flush()

    async def flush(self) -> None:
        pass

    @abstractmethod
    async def get_member(self, room_id: RoomID, user_id: UserID) -> Optional[Member]:
        pass

    @abstractmethod
    async def set_member(self, room_id: RoomID, user_id: UserID,
                         member: Union[Member, MemberStateEventContent]) -> None:
        pass

    @abstractmethod
    async def set_membership(self, room_id: RoomID, user_id: UserID, membership: Membership
                             ) -> None:
        pass

    @abstractmethod
    async def get_members(self, room_id: RoomID) -> Optional[List[UserID]]:
        pass

    @abstractmethod
    async def set_members(self, room_id: RoomID,
                          members: Dict[UserID, Union[Member, MemberStateEventContent]],
                          joined_only: bool = False) -> None:
        pass

    @abstractmethod
    async def has_full_member_list(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    async def has_power_levels_cached(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    async def get_power_levels(self, room_id: RoomID) -> Optional[PowerLevelStateEventContent]:
        pass

    @abstractmethod
    async def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent
                               ) -> None:
        pass

    @abstractmethod
    async def has_encryption_info_cached(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    async def is_encrypted(self, room_id: RoomID) -> Optional[bool]:
        pass

    @abstractmethod
    async def get_encryption_info(self, room_id: RoomID
                                  ) -> Optional[RoomEncryptionStateEventContent]:
        pass

    @abstractmethod
    async def set_encryption_info(self, room_id: RoomID, content: RoomEncryptionStateEventContent
                                  ) -> None:
        pass

    async def update_state(self, evt: StateEvent) -> None:
        if evt.type == EventType.ROOM_POWER_LEVELS:
            await self.set_power_levels(evt.room_id, evt.content)
        elif evt.type == EventType.ROOM_MEMBER:
            await self.set_member(evt.room_id, UserID(evt.state_key), evt.content)
        elif evt.type == EventType.ROOM_ENCRYPTION:
            await self.set_encryption_info(evt.room_id, evt.content)

    async def get_membership(self, room_id: RoomID, user_id: UserID) -> Membership:
        member = await self.get_member(room_id, user_id)
        return member.membership if member else Membership.LEAVE

    async def is_joined(self, room_id: RoomID, user_id: UserID) -> bool:
        return (await self.get_membership(room_id, user_id)) == Membership.JOIN

    def joined(self, room_id: RoomID, user_id: UserID) -> Awaitable[None]:
        return self.set_membership(room_id, user_id, Membership.JOIN)

    def invited(self, room_id: RoomID, user_id: UserID) -> Awaitable[None]:
        return self.set_membership(room_id, user_id, Membership.INVITE)

    def left(self, room_id: RoomID, user_id: UserID) -> Awaitable[None]:
        return self.set_membership(room_id, user_id, Membership.LEAVE)

    async def has_power_level(self, room_id: RoomID, user_id: UserID, event_type: EventType
                              ) -> Optional[bool]:
        room_levels = await self.get_power_levels(room_id)
        if not room_levels:
            return None
        return room_levels.get_user_level(user_id) >= room_levels.get_event_level(event_type)
