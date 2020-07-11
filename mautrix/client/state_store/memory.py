# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, Dict, Optional, Any

from .abstract import StateStore
from mautrix.types import (Member, MemberStateEventContent, Membership, PowerLevelStateEventContent,
                           RoomEncryptionStateEventContent, RoomID, UserID)


class MemoryStateStore(StateStore):
    members: Dict[RoomID, Dict[UserID, Member]]
    power_levels: Dict[RoomID, PowerLevelStateEventContent]
    encryption: Dict[RoomID, RoomEncryptionStateEventContent]

    def __init__(self) -> None:
        self.members = {}
        self.power_levels = {}
        self.encryption = {}

    def serialize(self) -> Dict[str, Any]:
        return {
            "members": {room_id: {user_id: member.serialize()
                                  for user_id, member in members.items()}
                        for room_id, members in self.members.items()},
            "power_levels": {room_id: content.serialize()
                             for room_id, content in self.power_levels.items()},
            "encryption": {room_id: content.serialize()
                           for room_id, content in self.encryption.items()},
        }

    def deserialize(self, data: Dict[str, Any]) -> None:
        self.members = {room_id: {user_id: Member.deserialize(member)
                                  for user_id, member in members.items()}
                        for room_id, members in data["members"].items()}
        self.power_levels = {room_id: PowerLevelStateEventContent.deserialize(content)
                             for room_id, content in data["power_levels"].items()}
        self.encryption = {room_id: RoomEncryptionStateEventContent.deserialize(content)
                           for room_id, content in data["encryption"].items()}

    async def get_member(self, room_id: RoomID, user_id: UserID) -> Optional[Member]:
        try:
            return self.members[room_id][user_id]
        except KeyError:
            return None

    async def set_member(self, room_id: RoomID, user_id: UserID,
                         member: Union[Member, MemberStateEventContent]) -> None:
        if isinstance(member, MemberStateEventContent):
            member = Member(membership=member.membership, avatar_url=member.avatar_url,
                            displayname=member.displayname)
        try:
            self.members[room_id][user_id] = member
        except KeyError:
            self.members[room_id] = {user_id: member}

    async def set_membership(self, room_id: RoomID, user_id: UserID,
                             membership: Membership) -> None:
        try:
            room_members = self.members[room_id]
        except KeyError:
            self.members[room_id] = {user_id: Member(membership=membership)}
            return
        try:
            room_members[user_id].membership = membership
        except (KeyError, TypeError):
            room_id[user_id] = Member(membership=membership)

    async def has_power_levels_cached(self, room_id: RoomID) -> bool:
        return room_id in self.power_levels

    async def get_power_levels(self, room_id: RoomID) -> Optional[PowerLevelStateEventContent]:
        return self.power_levels.get(room_id)

    async def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent) -> None:
        self.power_levels[room_id] = content

    async def has_encryption_cached(self, room_id: RoomID) -> bool:
        return room_id in self.encryption

    async def get_encryption(self, room_id: RoomID) -> RoomEncryptionStateEventContent:
        return self.encryption.get(room_id)

    async def set_encryption(self, room_id: RoomID,
                             content: RoomEncryptionStateEventContent) -> None:
        self.encryption[room_id] = content
