from typing import NewType, Union, Dict, List

UserID = NewType("UserID", str)
EventID = NewType("EventID", str)
RoomID = NewType("RoomID", str)
RoomAlias = NewType("RoomAlias", str)

JSON = Union[str, int, float, bool, None, Dict[str, 'JSON'], List['JSON']]
MatrixEvent = NewType("MatrixEvent", JSON)
