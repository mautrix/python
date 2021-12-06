# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
import sys

from mautrix.types import (
    Member,
    Membership,
    MemberStateEventContent,
    PowerLevelStateEventContent,
    RoomEncryptionStateEventContent,
    RoomID,
    UserID,
)

from .abstract import StateStore

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class SerializedStateStore(TypedDict):
    members: dict[RoomID, dict[UserID, Any]]
    full_member_list: dict[RoomID, bool]
    power_levels: dict[RoomID, Any]
    encryption: dict[RoomID, Any]


class MemoryStateStore(StateStore):
    members: dict[RoomID, dict[UserID, Member]]
    full_member_list: dict[RoomID, bool]
    power_levels: dict[RoomID, PowerLevelStateEventContent]
    encryption: dict[RoomID, RoomEncryptionStateEventContent | None]

    def __init__(self) -> None:
        self.members = {}
        self.full_member_list = {}
        self.power_levels = {}
        self.encryption = {}

    def serialize(self) -> SerializedStateStore:
        """
        Convert the data in the store into a JSON-friendly dict.

        Returns: A dict that can be safely serialized with most object serialization methods.
        """
        return {
            "members": {
                room_id: {user_id: member.serialize() for user_id, member in members.items()}
                for room_id, members in self.members.items()
            },
            "full_member_list": self.full_member_list,
            "power_levels": {
                room_id: content.serialize() for room_id, content in self.power_levels.items()
            },
            "encryption": {
                room_id: (content.serialize() if content is not None else None)
                for room_id, content in self.encryption.items()
            },
        }

    def deserialize(self, data: SerializedStateStore) -> None:
        """
        Parse a previously serialized dict into this state store.

        Args:
            data: A dict returned by :meth:`serialize`.
        """
        self.members = {
            room_id: {user_id: Member.deserialize(member) for user_id, member in members.items()}
            for room_id, members in data["members"].items()
        }
        self.full_member_list = data["full_member_list"]
        self.power_levels = {
            room_id: PowerLevelStateEventContent.deserialize(content)
            for room_id, content in data["power_levels"].items()
        }
        self.encryption = {
            room_id: (
                RoomEncryptionStateEventContent.deserialize(content)
                if content is not None
                else None
            )
            for room_id, content in data["encryption"].items()
        }

    async def get_member(self, room_id: RoomID, user_id: UserID) -> Member | None:
        try:
            return self.members[room_id][user_id]
        except KeyError:
            return None

    async def set_member(
        self, room_id: RoomID, user_id: UserID, member: Member | MemberStateEventContent
    ) -> None:
        if not isinstance(member, Member):
            member = Member(
                membership=member.membership,
                avatar_url=member.avatar_url,
                displayname=member.displayname,
            )
        try:
            self.members[room_id][user_id] = member
        except KeyError:
            self.members[room_id] = {user_id: member}

    async def set_membership(
        self, room_id: RoomID, user_id: UserID, membership: Membership
    ) -> None:
        try:
            room_members = self.members[room_id]
        except KeyError:
            self.members[room_id] = {user_id: Member(membership=membership)}
            return
        try:
            room_members[user_id].membership = membership
        except (KeyError, TypeError):
            room_members[user_id] = Member(membership=membership)

    async def get_member_profiles(
        self,
        room_id: RoomID,
        memberships: tuple[Membership, ...] = (Membership.JOIN, Membership.INVITE),
    ) -> dict[UserID, Member]:
        try:
            return {
                user_id: member
                for user_id, member in self.members[room_id].items()
                if member.membership in memberships
            }
        except KeyError:
            return {}

    async def set_members(
        self,
        room_id: RoomID,
        members: dict[UserID, Member | MemberStateEventContent],
        only_membership: Membership | None = None,
    ) -> None:
        old_members = {}
        if only_membership is not None:
            old_members = {
                user_id: member
                for user_id, member in self.members.get(room_id, {}).items()
                if member.membership != only_membership
            }
        self.members[room_id] = {
            user_id: (
                member
                if isinstance(member, Member)
                else Member(
                    membership=member.membership,
                    avatar_url=member.avatar_url,
                    displayname=member.displayname,
                )
            )
            for user_id, member in members.items()
        }
        self.members[room_id].update(old_members)
        self.full_member_list[room_id] = True

    async def has_full_member_list(self, room_id: RoomID) -> bool:
        return self.full_member_list.get(room_id, False)

    async def has_power_levels_cached(self, room_id: RoomID) -> bool:
        return room_id in self.power_levels

    async def get_power_levels(self, room_id: RoomID) -> PowerLevelStateEventContent | None:
        return self.power_levels.get(room_id)

    async def set_power_levels(
        self, room_id: RoomID, content: PowerLevelStateEventContent
    ) -> None:
        self.power_levels[room_id] = content

    async def has_encryption_info_cached(self, room_id: RoomID) -> bool:
        return room_id in self.encryption

    async def is_encrypted(self, room_id: RoomID) -> bool | None:
        try:
            return self.encryption[room_id] is not None
        except KeyError:
            return None

    async def get_encryption_info(self, room_id: RoomID) -> RoomEncryptionStateEventContent:
        return self.encryption.get(room_id)

    async def set_encryption_info(
        self, room_id: RoomID, content: RoomEncryptionStateEventContent
    ) -> None:
        self.encryption[room_id] = content
