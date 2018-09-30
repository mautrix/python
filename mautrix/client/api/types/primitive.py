from typing import NewType

UserID = NewType("UserID", str)
EventID = NewType("EventID", str)
RoomID = NewType("RoomID", str)
RoomAlias = NewType("RoomAlias", str)

FilterID = NewType("FilterID", str)

ContentURI = NewType("ContentURI", str)

SyncToken = NewType("SyncToken", str)
