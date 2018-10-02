from typing import List, NamedTuple
import attr

from .primitive import UserID
from .util import SerializableAttrs


@attr.s(auto_attribs=True)
class User(SerializableAttrs['User']):
    user_id: UserID
    avatar_url: str = None
    displayname: str = None


UserSearchResults = NamedTuple("UserSearchResults", results=List[User], limit=int)
