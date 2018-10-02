from ...errors import MatrixResponseError
from ...api import Method
from .base import BaseClientAPI
from .types import UserID, Filter, FilterID


class FilteringMethods(BaseClientAPI):
    """
    Methods in section 7 Filtering of the spec.

    Filters can be created on the server and can be passed as as a parameter to APIs which return
    events. These filters alter the data returned from those APIs. Not all APIs accept filters.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#filtering>`__
    """

    async def get_filter(self, user_id: UserID, filter_id: FilterID) -> Filter:
        """
        Download a filter.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-user-userid-filter-filterid>`__

        Args:
            user_id: The user ID to download a filter for.
            filter_id: The filter ID to download.

        Returns:
            The filter data.
        """
        content = await self.api.request(Method.GET, f"/user/{user_id}/filter/{filter_id}")
        return Filter.deserialize(content)

    async def create_filter(self, user_id: UserID, filter_params: Filter) -> FilterID:
        """
        Upload a new filter definition to the homeserver.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-user-userid-filter>`__

        Args:
            user_id: The ID of the user uploading the filter.
            filter_params: The filter data.

        Returns:
            A filter ID that can be used in future requests to refer to the uploaded filter.
        """
        resp = await self.api.request(Method.POST, f"/user/{user_id}/filter",
                                      filter_params.serialize())
        try:
            return resp["filter_id"]
        except KeyError:
            raise MatrixResponseError("`filter_id` not in response.")

    # endregion
