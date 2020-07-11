# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, AsyncIterable, Union

from mautrix.api import Method, MediaPath
from mautrix.errors import MatrixResponseError
from mautrix.types import ContentURI, MediaRepoConfig, SerializerError, MXOpenGraph

from ..base import BaseClientAPI

try:
    import magic
except ImportError:
    magic = None  # type: ignore


class MediaRepositoryMethods(BaseClientAPI):
    """
    Methods in section 13.8 Content Repository of the spec. These methods are used for uploading and
    downloading content from the media repository and for getting URL previews without leaking
    client IPs.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#id112>`__"""

    async def upload_media(self, data: Union[bytes, AsyncIterable[bytes]],
                           mime_type: Optional[str] = None, filename: Optional[str] = None,
                           size: Optional[int] = None) -> ContentURI:
        """
        Upload a file to the content repository.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#post-matrix-media-r0-upload>`__

        Args:
            data: The data to upload.
            mime_type: The MIME type to send with the upload request.
            filename: The filename to send with the upload request.
            size: The file size to send with the upload request.

        Returns:
            The MXC URI to the uploaded file.

        Raises:
            MatrixResponseError: If the response does not contain a ``content_uri`` field.
        """
        if magic and isinstance(data, bytes):
            mime_type = mime_type or magic.from_buffer(data, mime=True)
        headers = {}
        if mime_type:
            headers["Content-Type"] = mime_type
        if size:
            headers["Content-Length"] = str(size)
        query = {}
        if filename:
            query["filename"] = filename
        resp = await self.api.request(Method.POST, MediaPath.upload, content=data,
                                      headers=headers, query_params=query)
        try:
            return resp["content_uri"]
        except KeyError:
            raise MatrixResponseError("`content_uri` not in response.")

    async def download_media(self, url: ContentURI) -> bytes:
        """
        Download a file from the content repository.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-media-r0-download-servername-mediaid>`__

        Args:
            url: The MXC URI to download.

        Returns:
            The raw downloaded data.
        """
        url = self.api.get_download_url(url)
        async with self.api.session.get(url) as response:
            return await response.read()

    async def download_thumbnail(self, url: ContentURI,
                                 width: Optional[int] = None, height: Optional[int] = None,
                                 resize_method: Optional[str] = None, allow_remote: bool = True):
        """
        Download a thumbnail for a file in the content repository.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-media-r0-thumbnail-servername-mediaid>`__

        Args:
            url: The MXC URI to download.
            width: The _desired_ width of the thumbnail. The actual thumbnail may not match the size
                specified.
            height: The _desired_ height of the thumbnail. The actual thumbnail may not match the
                size specified.
            resize_method: The desired resizing method. Either ``crop`` or ``scale``.
            allow_remote: Indicates to the server that it should not attempt to fetch the media if
                it is deemed remote. This is to prevent routing loops where the server contacts
                itself.

        Returns:
            The raw downloaded data.
        """
        url = self.api.get_download_url(url, download_type="thumbnail")
        query_params = {}
        if width is not None:
            query_params["width"] = width
        if height is not None:
            query_params["height"] = height
        if resize_method is not None:
            query_params["resize_method"] = resize_method
        if allow_remote is not None:
            query_params["allow_remote"] = allow_remote
        async with self.api.session.get(url, params=query_params) as response:
            return await response.read()

    async def get_url_preview(self, url: str, timestamp: Optional[int] = None) -> MXOpenGraph:
        """
        Get information about a URL for a client.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-media-r0-preview-url>`__

        Args:
            url: The URL to get a preview of.
            timestamp: The preferred point in time to return a preview for. The server may return a
                newer version if it does not have the requested version available.
        """
        query_params = {"url": url}
        if timestamp is not None:
            query_params["ts"] = timestamp
        content = await self.api.request(Method.GET, MediaPath.preview_url,
                                         query_params=query_params)
        try:
            return MXOpenGraph.deserialize(content)
        except SerializerError as e:
            raise MatrixResponseError("Invalid MXOpenGraph in response.") from e

    async def get_media_repo_config(self) -> MediaRepoConfig:
        """
        This endpoint allows clients to retrieve the configuration of the content repository, such
        as upload limitations. Clients SHOULD use this as a guide when using content repository
        endpoints. All values are intentionally left optional. Clients SHOULD follow the advice
        given in the field description when the field is not available.

        **NOTE:** Both clients and server administrators should be aware that proxies between the
        client and the server may affect the apparent behaviour of content repository APIs, for
        example, proxies may enforce a lower upload size limit than is advertised by the server on
        this endpoint.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-media-r0-config>`__

        Returns:
            The media repository config.
        """
        content = await self.api.request(Method.GET, MediaPath.config)
        try:
            return MediaRepoConfig.deserialize(content)
        except SerializerError as e:
            raise MatrixResponseError("Invalid MediaRepoConfig in response") from e
