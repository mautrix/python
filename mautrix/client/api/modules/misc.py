from ..base import BaseClientAPI


class MiscModuleMethods(BaseClientAPI):
    """
    Miscellaneous subsections in the `Modules section`_ of the API spec.

    Currently included subsections:

    * 13.4 `Typing Notifications`_
    * 13.5 `Receipts`_
    * 13.6 `Fully Read Markers`_
    * 13.7 `Presence`_

    .. _Modules section: https://matrix.org/docs/spec/client_server/r0.4.0.html#modules
    .. _Typing Notifications: https://matrix.org/docs/spec/client_server/r0.4.0.html#id95
    .. _Receipts: https://matrix.org/docs/spec/client_server/r0.4.0.html#id99
    .. _Fully Read Markers: https://matrix.org/docs/spec/client_server/r0.4.0.html#fully-read-markers
    .. _Presence: https://matrix.org/docs/spec/client_server/r0.4.0.html#id107
    """

    # region 13.4 Typing Notifications

    async def set_typing(self):
        pass

    # endregion
    # region 13.5 Receipts

    async def send_receipt(self):
        pass

    async def mark_read(self):
        pass

    # endregion
    # region 13.6 Fully read markers

    async def mark_fully_read(self):
        pass

    # endregion
    # region 13.7 Presence

    async def set_presence(self):
        pass

    async def get_presence(self):
        pass

    # endregion
