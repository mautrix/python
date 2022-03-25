# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, AsyncIterable, Literal
import asyncio

from mautrix import __optional_imports__
from mautrix.api import MediaPath, Method
from mautrix.errors import MatrixResponseError
from mautrix.types import ContentURI, MediaRepoConfig, MXOpenGraph, SerializerError

from ..base import BaseClientAPI

try:
    from mautrix.util import magic
except ImportError:
    if __optional_imports__:
        raise
    magic = None  # type: ignore


class MediaRepositoryMethods(BaseClientAPI):
    """
    Methods in section 13.8 Content Repository of the spec. These methods are used for uploading and
    downloading content from the media repository and for getting URL previews without leaking
    client IPs.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#id112>`__

    There are also methods for supporting `MSC2246
    <https://github.com/matrix-org/matrix-spec-proposals/pull/2246>`__ which allows asynchronous
    uploads of media.
    """

    async def unstable_create_mxc(self) -> ContentURI:
        """
        Create a media ID for uploading media to the homeserver. Requires the homeserver to have
        `MSC2246 <https://github.com/matrix-org/matrix-spec-proposals/pull/2246>`__ support.

        Returns:
            The MXC URI that can be used to upload a file to later.

        Raises:
            MatrixResponseError: If the response does not contain a ``content_uri`` field.
        """
        resp = await self.api.request(Method.POST, MediaPath.unstable["fi.mau.msc2246"].create)
        try:
            return resp["content_uri"]
        except KeyError:
            raise MatrixResponseError("`content_uri` not in response.")

    async def upload_media(
        self,
        data: bytes | bytearray | AsyncIterable[bytes],
        mime_type: str | None = None,
        filename: str | None = None,
        size: int | None = None,
        mxc: ContentURI | None = None,
        async_upload: bool = False,
    ) -> ContentURI:
        """
        Upload a file to the content repository.

        See also: `API reference <https://spec.matrix.org/v1.2/client-server-api/#post_matrixmediav3upload>`__

        Args:
            data: The data to upload.
            mime_type: The MIME type to send with the upload request.
            filename: The filename to send with the upload request.
            size: The file size to send with the upload request.
            mxc: An existing MXC URI which doesn't have content yet to upload into. Requires the
                homeserver to have MSC2246_ support.
            async_upload: Should the media be uploaded in the background (using MSC2246_)?
                If ``True``, this will create a MXC URI, start uploading in the background and then
                immediately return the created URI. This is mutually exclusive with manually
                passing the ``mxc`` parameter.

        .. _MSC2246: https://github.com/matrix-org/matrix-spec-proposals/pull/2246

        Returns:
            The MXC URI to the uploaded file.

        Raises:
            MatrixResponseError: If the response does not contain a ``content_uri`` field.
            ValueError: if both ``async_upload`` and ``mxc`` are provided at the same time.
        """
        if magic and isinstance(data, bytes):
            mime_type = mime_type or magic.mimetype(data)
        headers = {}
        if mime_type:
            headers["Content-Type"] = mime_type
        if size:
            headers["Content-Length"] = str(size)
        query = {}
        if filename:
            query["filename"] = filename

        if async_upload:
            if mxc:
                raise ValueError("async_upload and mxc can't be provided simultaneously")
            mxc = await self.unstable_create_mxc()

        path = MediaPath.v3.upload
        method = Method.POST
        if mxc:
            server_name, media_id = self.api.parse_mxc_uri(mxc)
            path = MediaPath.unstable["fi.mau.msc2246"].upload[server_name][media_id]
            method = Method.PUT

        task = self.api.request(method, path, content=data, headers=headers, query_params=query)
        if async_upload:

            async def _try_upload():
                try:
                    await task
                except Exception as e:
                    self.log.error(f"Failed to upload {mxc}: {type(e).__name__}: {e}")

            asyncio.create_task(_try_upload())
            return mxc
        else:
            resp = await task
            try:
                return resp["content_uri"]
            except KeyError:
                raise MatrixResponseError("`content_uri` not in response.")

    async def download_media(self, url: ContentURI, max_stall_ms: int | None = None) -> bytes:
        """
        Download a file from the content repository.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#get-matrix-media-r0-download-servername-mediaid>`__

        Args:
            url: The MXC URI to download.
            max_stall_ms: The maximum number of milliseconds that the client is willing to wait to
                start receiving data. Used for MSC2246 Asynchronous Uploads.

        Returns:
            The raw downloaded data.
        """
        url = self.api.get_download_url(url)
        query_params: dict[str, Any] = {}
        if max_stall_ms is not None:
            query_params["max_stall_ms"] = max_stall_ms
            query_params["fi.mau.msc2246.max_stall_ms"] = max_stall_ms
        async with self.api.session.get(url, params=query_params) as response:
            return await response.read()

    async def download_thumbnail(
        self,
        url: ContentURI,
        width: int | None = None,
        height: int | None = None,
        resize_method: Literal["crop", "scale"] = None,
        allow_remote: bool = True,
        max_stall_ms: int | None = None,
    ):
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
            max_stall_ms: The maximum number of milliseconds that the client is willing to wait to
                start receiving data. Used for MSC2246 Asynchronous Uploads.

        Returns:
            The raw downloaded data.
        """
        url = self.api.get_download_url(url, download_type="thumbnail")
        query_params: dict[str, Any] = {}
        if width is not None:
            query_params["width"] = width
        if height is not None:
            query_params["height"] = height
        if resize_method is not None:
            query_params["method"] = resize_method
        if allow_remote is not None:
            query_params["allow_remote"] = allow_remote
        if max_stall_ms is not None:
            query_params["max_stall_ms"] = max_stall_ms
            query_params["fi.mau.msc2246.max_stall_ms"] = max_stall_ms
        async with self.api.session.get(url, params=query_params) as response:
            return await response.read()

    async def get_url_preview(self, url: str, timestamp: int | None = None) -> MXOpenGraph:
        """
        Get information about a URL for a client.

        See also: `API reference <https://spec.matrix.org/v1.2/client-server-api/#get_matrixmediav3preview_url>`__

        Args:
            url: The URL to get a preview of.
            timestamp: The preferred point in time to return a preview for. The server may return a
                newer version if it does not have the requested version available.
        """
        query_params = {"url": url}
        if timestamp is not None:
            query_params["ts"] = timestamp
        content = await self.api.request(
            Method.GET, MediaPath.v3.preview_url, query_params=query_params
        )
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
        content = await self.api.request(Method.GET, MediaPath.v3.config)
        try:
            return MediaRepoConfig.deserialize(content)
        except SerializerError as e:
            raise MatrixResponseError("Invalid MediaRepoConfig in response") from e
