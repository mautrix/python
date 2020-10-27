# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, Dict, Optional, Any, List

from .abstract import StateStore
from mautrix.types import (Member, MemberStateEventContent, Membership, PowerLevelStateEventContent,
                           RoomEncryptionStateEventContent, RoomID, UserID)


class MemoryStateStore(StateStore):
    members: Dict[RoomID, Dict[UserID, Member]]
    full_member_list: Dict[RoomID, bool]
    power_levels: Dict[RoomID, PowerLevelStateEventContent]
    encryption: Dict[RoomID, Optional[RoomEncryptionStateEventContent]]

    def __init__(self) -> None:
        self.members = {}
        self.full_member_list = {}
        self.power_levels = {}
        self.encryption = {}

    def serialize(self) -> Dict[str, Any]:
        return {
            "members": {room_id: {user_id: member.serialize()
                                  for user_id, member in members.items()}
                        for room_id, members in self.members.items()},
            "full_member_list": self.full_member_list,
            "power_levels": {room_id: content.serialize()
                             for room_id, content in self.power_levels.items()},
            "encryption": {room_id: (content.serialize() if content is not None else None)
                           for room_id, content in self.encryption.items()},
        }

    def deserialize(self, data: Dict[str, Any]) -> None:
        self.members = {room_id: {user_id: Member.deserialize(member)
                                  for user_id, member in members.items()}
                        for room_id, members in data["members"].items()}
        self.full_member_list = data["full_member_list"]
        self.power_levels = {room_id: PowerLevelStateEventContent.deserialize(content)
                             for room_id, content in data["power_levels"].items()}
        self.encryption = {room_id: (RoomEncryptionStateEventContent.deserialize(content)
                                     if content is not None else None)
                           for room_id, content in data["encryption"].items()}

    async def get_member(self, room_id: RoomID, user_id: UserID) -> Optional[Member]:
        try:
            return self.members[room_id][user_id]
        except KeyError:
            return None

    async def set_member(self, room_id: RoomID, user_id: UserID,
                         member: Union[Member, MemberStateEventContent]) -> None:
        if not isinstance(member, Member):
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

    async def get_members(self, room_id: RoomID) -> Optional[List[UserID]]:
        try:
            return [user_id for user_id, member in self.members[room_id]
                    if (member.membership == Membership.JOIN
                        or member.membership == Membership.INVITE)]
        except KeyError:
            return None

    async def set_members(self, room_id: RoomID,
                          members: Dict[UserID, Union[Member, MemberStateEventContent]]) -> None:
        self.members[room_id] = {user_id: (member if isinstance(member, Member)
                                           else Member(membership=member.membership,
                                                       avatar_url=member.avatar_url,
                                                       displayname=member.displayname))
                                 for user_id, member in members.items()}
        self.full_member_list[room_id] = True

    async def has_full_member_list(self, room_id: RoomID) -> bool:
        return self.full_member_list.get(room_id, False)

    async def has_power_levels_cached(self, room_id: RoomID) -> bool:
        return room_id in self.power_levels

    async def get_power_levels(self, room_id: RoomID) -> Optional[PowerLevelStateEventContent]:
        return self.power_levels.get(room_id)

    async def set_power_levels(self, room_id: RoomID, content: PowerLevelStateEventContent) -> None:
        self.power_levels[room_id] = content

    async def has_encryption_info_cached(self, room_id: RoomID) -> bool:
        return room_id in self.encryption

    async def is_encrypted(self, room_id: RoomID) -> Optional[bool]:
        try:
            return self.encryption[room_id] is not None
        except KeyError:
            return None

    async def get_encryption_info(self, room_id: RoomID) -> RoomEncryptionStateEventContent:
        return self.encryption.get(room_id)

    async def set_encryption_info(self, room_id: RoomID,
                                  content: RoomEncryptionStateEventContent) -> None:
        self.encryption[room_id] = content
