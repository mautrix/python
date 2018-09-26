from .base import BaseClientAPI


class UserDataMethods(BaseClientAPI):
    """
    Methods in section 10 User Data of the spec. See also: `API reference`_

    .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#user-data
    """

    # region 10.1 User Directory
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#user-directory

    async def search_users(self):
        pass

    # endregion
    # region 10.2 Profiles
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#profiles

    async def set_displayname(self):
        pass

    async def get_displayname(self):
        pass

    async def set_avatar_url(self):
        pass

    async def get_avatar_url(self):
        pass

    async def get_profile(self):
        pass

    # endregion
