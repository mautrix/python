from .base import BaseClientAPI


class RoomMethods(BaseClientAPI):
    """
    Methods in section 9 Rooms of the spec. See also: `API reference`_

    .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#rooms
    """

    # region 9.1 Creation
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#creation

    async def create_room(self):
        pass

    # endregion
    # region 9.2 Room aliases
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#room-aliases

    async def add_room_alias(self):
        pass

    async def remove_room_alias(self):
        pass

    async def get_room_alias(self):
        pass

    # endregion
    # region 9.4 Room membership
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#room-membership

    async def get_joined_rooms(self):
        pass

    # region 9.4.2 Joining rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#joining-rooms

    async def join_room_by_id(self):
        pass

    async def join_room(self):
        pass

    async def invite_user(self):
        pass

    # endregion
    # region 9.4.3 Leaving rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#leaving-rooms

    async def leave_room(self):
        pass

    async def forget_room(self):
        pass

    async def kick_user(self):
        pass

    # endregion
    # region 9.4.4 Banning users in a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#banning-users-in-a-room

    async def ban_user(self):
        pass

    async def unban_user(self):
        pass

    # endregion

    # endregion
    # region 9.5 Listing rooms
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#listing-rooms

    def get_room_directory_visibility(self):
        pass

    def set_room_directory_visibility(self):
        pass

    def get_room_directory(self):
        pass

    def get_filtered_room_directory(self):
        pass

    # endregion
