from typing import Awaitable, Dict

from .base import BaseClientAPI


class FilteringMethods(BaseClientAPI):
    """
    Methods in section 7 Filtering of the spec. See also: `API reference`_

    Filters can be created on the server and can be passed as as a parameter to APIs which return
    events. These filters alter the data returned from those APIs. Not all APIs accept filters.

    .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#filtering
    """

    def get_filter(self, user_id: str, filter_id: str) -> Awaitable[Dict]:
        """
        Download a filter. See also: `API reference`_

        Args:
            user_id: The user ID to download a filter for.
            filter_id: The filter ID to download.

        Returns:
            The filter data.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-user-userid-filter-filterid
        """
        return self.client.request("GET", f"/user/{user_id}/filter/{filter_id}")

    async def create_filter(self, user_id: str, filter_params: Dict) -> str:
        """
        Upload a new filter definition to the homeserver. See also: `API reference`_

        Args:
            user_id: The ID of the user uploading the filter.
            filter_params: The filter data.

        Returns:
            A filter ID that can be used in future requests to refer to the uploaded filter.

        .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-user-userid-filter
        """
        resp = await self.client.request("POST", f"/user/{user_id}/filter", filter_params)
        return resp.get("filter_id", None)

    # endregion
