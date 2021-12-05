# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, NamedTuple

from attr import dataclass

from .event import Membership
from .primitive import ContentURI, UserID
from .util import SerializableAttrs


@dataclass
class Member(SerializableAttrs):
    membership: Membership = None
    avatar_url: ContentURI = None
    displayname: str = None


@dataclass
class User(SerializableAttrs):
    user_id: UserID
    avatar_url: ContentURI = None
    displayname: str = None


class UserSearchResults(NamedTuple):
    results: List[User]
    limit: int
