from .filtering import FilteringMethods
from .events import EventMethods
from .rooms import RoomMethods
from .user_data import UserDataMethods
from .modules import ModuleMethods


class ClientAPI(FilteringMethods, EventMethods, RoomMethods, UserDataMethods, ModuleMethods):
    """
    ClientAPI is a medium-level wrapper around the HTTPAPI that provides many easy-to-use
    functions for accessing the client-server API.
    """
    pass
