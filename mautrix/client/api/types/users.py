from typing import List, NamedTuple
import attr

from .primitive import UserID
from .util import SerializableAttrs
from .event import Member


@attr.s(auto_attribs=True)
class User(Member, SerializableAttrs['User']):
    user_id: UserID = None


UserSearchResults = NamedTuple("UserSearchResults", results=List[User], limit=int)
