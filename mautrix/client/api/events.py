from typing import Awaitable, Dict

from .base import BaseClientAPI


class EventMethods(BaseClientAPI):
    """
    Methods in section 8 Events of the spec. See also: `API reference`_

    .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#events
    """

    # region 8.2 Syncing
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#syncing

    def sync(self, since: str = None, timeout_ms: int = 30000, filter_id: int = None,
             full_state: bool = None, set_presence: str = None) -> Awaitable[Dict]:
        """
        Perform a sync request. See also: `API reference`_

        Args:
            since (str): Optional. A token which specifies where to continue a sync from.
            timeout_ms (int): Optional. The time in milliseconds to wait.
            filter_id (int): A filter ID.
            full_state (bool): Return the full state for every room the user has joined
                Defaults to false.
            set_presence (str): Should the client be marked as "online" or" offline"

        .. _API reference:
            https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-sync
        """
        request = {"timeout": timeout_ms}
        if since:
            request["since"] = since
        if filter_id:
            request["filter"] = filter_id
        if full_state:
            request["full_state"] = "true"
        if set_presence:
            request["set_presence"] = set_presence
        return self.client.request("GET", "/sync", query_params=request)

    # endregion
    # region 8.3 Getting events for a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#getting-events-for-a-room

    async def get_event(self):
        pass

    async def get_state_event(self):
        pass

    async def get_state(self):
        pass

    async def get_members(self):
        pass

    async def get_joined_members(self):
        pass

    async def get_messages(self):
        pass

    # endregion
    # region 8.4 Sending events to a room
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#sending-events-to-a-room

    async def send_state_event(self):
        pass

    async def send_message_event(self):
        pass

    # endregion
    # region 8.5 Redactions
    # API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#redactions

    async def redact(self):
        pass

    # endregion
