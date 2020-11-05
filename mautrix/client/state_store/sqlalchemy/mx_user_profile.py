# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Iterable, Dict

from sqlalchemy import Column, Text, Enum

from mautrix.types import RoomID, UserID, ContentURI, Member, Membership
from mautrix.util.db import Base

from .mx_room_state import RoomState


class UserProfile(Base):
    __tablename__ = "mx_user_profile"

    room_id: RoomID = Column(Text, primary_key=True)
    user_id: UserID = Column(Text, primary_key=True)
    membership: Membership = Column(Enum(Membership), nullable=False, default=Membership.LEAVE)
    displayname: str = Column(Text, nullable=True)
    avatar_url: ContentURI = Column(Text, nullable=True)

    def member(self) -> Member:
        return Member(membership=self.membership, displayname=self.displayname,
                      avatar_url=self.avatar_url)

    @classmethod
    def get(cls, room_id: RoomID, user_id: UserID) -> Optional['UserProfile']:
        return cls._select_one_or_none((cls.c.room_id == room_id) & (cls.c.user_id == user_id))

    @classmethod
    def all_in_room(cls, room_id: RoomID, prefix: str = None, suffix: str = None, bot: str = None
                    ) -> Iterable['UserProfile']:
        clause = (((cls.c.membership == Membership.JOIN)
                   | (cls.c.membership == Membership.INVITE))
                  & (cls.c.room_id == room_id))
        if bot:
            clause = clause & (cls.c.user_id != bot)
        if prefix:
            clause = clause & ~cls.c.user_id.startswith(prefix, autoescape=True)
        if suffix:
            clause = clause & ~cls.c.user_id.startswith(suffix, autoescape=True)
        return cls._select_all(clause)

    @classmethod
    def find_rooms_with_user(cls, user_id: UserID) -> Iterable['UserProfile']:
        return cls._select_all((cls.c.user_id == user_id)
                               & (cls.c.room_id == RoomState.c.room_id)
                               & (RoomState.c.is_encrypted == True))

    @classmethod
    def delete_all(cls, room_id: RoomID) -> None:
        with cls.db.begin() as conn:
            conn.execute(cls.t.delete().where(cls.c.room_id == room_id))

    @classmethod
    def bulk_replace(cls, room_id: RoomID, members: Dict[UserID, Member]) -> None:
        with cls.db.begin() as conn:
            delete_condition = cls.c.room_id == room_id
            cls.db.execute(cls.t.delete().where(delete_condition))
            conn.execute(cls.t.insert(),
                         [dict(room_id=room_id, user_id=user_id, membership=member.membership,
                               displayname=member.displayname, avatar_url=member.avatar_url)
                          for user_id, member in members.items()])
