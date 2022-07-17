# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable
from abc import ABC, abstractmethod

from mautrix.types import (
    EventType,
    Member,
    Membership,
    MemberStateEventContent,
    PowerLevelStateEventContent,
    RoomEncryptionStateEventContent,
    RoomID,
    StateEvent,
    UserID,
)


class StateStore(ABC):
    async def open(self) -> None:
        pass

    async def close(self) -> None:
        await self.flush()

    async def flush(self) -> None:
        pass

    @abstractmethod
    async def get_member(self, room_id: RoomID, user_id: UserID) -> Member | None:
        pass

    @abstractmethod
    async def set_member(
        self, room_id: RoomID, user_id: UserID, member: Member | MemberStateEventContent
    ) -> None:
        pass

    @abstractmethod
    async def set_membership(
        self, room_id: RoomID, user_id: UserID, membership: Membership
    ) -> None:
        pass

    @abstractmethod
    async def get_member_profiles(
        self,
        room_id: RoomID,
        memberships: tuple[Membership, ...] = (Membership.JOIN, Membership.INVITE),
    ) -> dict[UserID, Member]:
        pass

    async def get_members(
        self,
        room_id: RoomID,
        memberships: tuple[Membership, ...] = (Membership.JOIN, Membership.INVITE),
    ) -> list[UserID]:
        profiles = await self.get_member_profiles(room_id, memberships)
        return list(profiles.keys())

    async def get_members_filtered(
        self,
        room_id: RoomID,
        not_prefix: str,
        not_suffix: str,
        not_id: str,
        memberships: tuple[Membership, ...] = (Membership.JOIN, Membership.INVITE),
    ) -> list[UserID]:
        """
        A filtered version of get_members that only returns user IDs that aren't operated by a
        bridge. This should return the same as :meth:`get_members`, except users where the user ID
        is equal to not_id OR it starts with not_prefix AND ends with not_suffix.

        The default implementation simply calls :meth:`get_members`, but databases can implement
        this more efficiently.

        Args:
            room_id: The room ID to find.
            not_prefix: The user ID prefix to disallow.
            not_suffix: The user ID suffix to disallow.
            not_id: The user ID to disallow.
            memberships: The membership states to include.
        """
        members = await self.get_members(room_id, memberships=memberships)
        return [
            user_id
            for user_id in members
            if user_id != not_id
            and not (user_id.startswith(not_prefix) and user_id.endswith(not_suffix))
        ]

    @abstractmethod
    async def set_members(
        self,
        room_id: RoomID,
        members: dict[UserID, Member | MemberStateEventContent],
        only_membership: Membership | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def has_full_member_list(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    async def has_power_levels_cached(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    async def get_power_levels(self, room_id: RoomID) -> PowerLevelStateEventContent | None:
        pass

    @abstractmethod
    async def set_power_levels(
        self, room_id: RoomID, content: PowerLevelStateEventContent
    ) -> None:
        pass

    @abstractmethod
    async def has_encryption_info_cached(self, room_id: RoomID) -> bool:
        pass

    @abstractmethod
    async def is_encrypted(self, room_id: RoomID) -> bool | None:
        pass

    @abstractmethod
    async def get_encryption_info(self, room_id: RoomID) -> RoomEncryptionStateEventContent | None:
        pass

    @abstractmethod
    async def set_encryption_info(
        self, room_id: RoomID, content: RoomEncryptionStateEventContent | dict[str, any]
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

    async def has_power_level(
        self, room_id: RoomID, user_id: UserID, event_type: EventType
    ) -> bool | None:
        room_levels = await self.get_power_levels(room_id)
        if not room_levels:
            return None
        return room_levels.get_user_level(user_id) >= room_levels.get_event_level(event_type)
