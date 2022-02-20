# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from mautrix.api import Method, Path
from mautrix.errors import MatrixResponseError
from mautrix.types import Filter, FilterID, Serializable

from .base import BaseClientAPI


class FilteringMethods(BaseClientAPI):
    """
    Methods in section 7 Filtering of the spec.

    Filters can be created on the server and can be passed as as a parameter to APIs which return
    events. These filters alter the data returned from those APIs. Not all APIs accept filters.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#filtering>`__
    """

    async def get_filter(self, filter_id: FilterID) -> Filter:
        """
        Download a filter.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-client-r0-user-userid-filter-filterid>`__

        Args:
            filter_id: The filter ID to download.

        Returns:
            The filter data.
        """
        content = await self.api.request(Method.GET, Path.v3.user[self.mxid].filter[filter_id])
        return Filter.deserialize(content)

    async def create_filter(self, filter_params: Filter) -> FilterID:
        """
        Upload a new filter definition to the homeserver.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-client-r0-user-userid-filter>`__

        Args:
            filter_params: The filter data.

        Returns:
            A filter ID that can be used in future requests to refer to the uploaded filter.
        """
        resp = await self.api.request(
            Method.POST,
            Path.v3.user[self.mxid].filter,
            filter_params.serialize()
            if isinstance(filter_params, Serializable)
            else filter_params,
        )
        try:
            return resp["filter_id"]
        except KeyError:
            raise MatrixResponseError("`filter_id` not in response.")

    # endregion
