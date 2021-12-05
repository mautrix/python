# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import json

from aiohttp import ClientError, ClientSession, ContentTypeError
from yarl import URL

from mautrix.api import HTTPAPI, Method
from mautrix.errors import (
    WellKnownInvalidVersionsResponse,
    WellKnownMissingHomeserver,
    WellKnownNotJSON,
    WellKnownNotURL,
    WellKnownUnexpectedStatus,
    WellKnownUnsupportedScheme,
)
from mautrix.types import DeviceID, SerializerError, UserID, VersionsResponse
from mautrix.util.logging import TraceLogger


class BaseClientAPI:
    """
    BaseClientAPI is the base class for :class:`ClientAPI`. This is separate from the main
    ClientAPI class so that the ClientAPI methods can be split into multiple classes (that
    inherit this class).All those section-specific method classes are inherited by the main
    ClientAPI class to create the full class.
    """

    localpart: str
    domain: str
    _mxid: UserID
    device_id: DeviceID
    api: HTTPAPI
    log: TraceLogger

    def __init__(
        self, mxid: UserID = "", device_id: DeviceID = "", api: HTTPAPI | None = None, **kwargs
    ) -> None:
        """
        Initialize a ClientAPI. You must either provide the ``api`` parameter with an existing
        :class:`mautrix.api.HTTPAPI` instance, or provide the ``base_url`` and other arguments for
        creating it as kwargs.

        Args:
            mxid: The Matrix ID of the user. This is used for things like setting profile metadata.
                  Additionally, the homeserver domain is extracted from this string and used for
                  setting aliases and such. This can be changed later using `set_mxid`.
            device_id: The device ID corresponding to the access token used.
            api: The :class:`mautrix.api.HTTPAPI` instance to use. You can also pass the ``kwargs``
                 to create a HTTPAPI instance rather than creating the instance yourself.
            kwargs: If ``api`` is not specified, then the arguments to pass when creating a HTTPAPI.
        """
        if mxid:
            self.mxid = mxid
        else:
            self._mxid = None
            self.localpart = None
            self.domain = None
        self.fill_member_event_callback = None
        self.device_id = device_id
        self.api = api or HTTPAPI(**kwargs)
        self.log = self.api.log

    @classmethod
    def parse_user_id(cls, mxid: UserID) -> tuple[str, str]:
        """
        Parse the localpart and server name from a Matrix user ID.

        Args:
            mxid: The Matrix user ID.

        Returns:
            A tuple of (localpart, server_name).

        Raises:
            ValueError: if the given user ID is invalid.
        """
        if len(mxid) == 0:
            raise ValueError("User ID is empty")
        elif mxid[0] != "@":
            raise ValueError("User IDs start with @")
        try:
            sep = mxid.index(":")
        except ValueError as e:
            raise ValueError("User ID must contain domain separator") from e
        if sep == len(mxid) - 1:
            raise ValueError("User ID must contain domain")
        return mxid[1:sep], mxid[sep + 1 :]

    @property
    def mxid(self) -> UserID:
        return self._mxid

    @mxid.setter
    def mxid(self, mxid: UserID) -> None:
        self.localpart, self.domain = self.parse_user_id(mxid)
        self._mxid = mxid

    async def versions(self) -> VersionsResponse:
        """Get client-server spec versions supported by the server."""
        resp = await self.api.request(Method.GET, "_matrix/client/versions")
        return VersionsResponse.deserialize(resp)

    @classmethod
    async def discover(cls, domain: str, session: ClientSession | None = None) -> URL | None:
        """
        Follow the server discovery spec to find the actual URL when given a Matrix server name.

        Args:
            domain: The server name (end of user ID) to discover.
            session: Optionally, the aiohttp ClientSession object to use.

        Returns:
            The parsed URL if the discovery succeeded.
            ``None`` if the request returned a 404 status.

        Raises:
            WellKnownError: for other errors
        """
        if session is None:
            async with ClientSession(headers={"User-Agent": HTTPAPI.default_ua}) as sess:
                return await cls._discover(domain, sess)
        else:
            return await cls._discover(domain, session)

    @classmethod
    async def _discover(cls, domain: str, session: ClientSession) -> URL | None:
        well_known = URL.build(scheme="https", host=domain, path="/.well-known/matrix/client")
        async with session.get(well_known) as resp:
            if resp.status == 404:
                return None
            elif resp.status != 200:
                raise WellKnownUnexpectedStatus(resp.status)
            try:
                data = await resp.json(content_type=None)
            except (json.JSONDecodeError, ContentTypeError) as e:
                raise WellKnownNotJSON() from e

        try:
            homeserver_url = data["m.homeserver"]["base_url"]
        except KeyError as e:
            raise WellKnownMissingHomeserver() from e
        parsed_url = URL(homeserver_url)
        if not parsed_url.is_absolute():
            raise WellKnownNotURL()
        elif parsed_url.scheme not in ("http", "https"):
            raise WellKnownUnsupportedScheme(parsed_url.scheme)

        try:
            async with session.get(parsed_url / "_matrix/client/versions") as resp:
                data = VersionsResponse.deserialize(await resp.json())
                if len(data.versions) == 0:
                    raise ValueError("no versions defined in /_matrix/client/versions response")
        except (ClientError, json.JSONDecodeError, SerializerError, ValueError) as e:
            raise WellKnownInvalidVersionsResponse() from e

        return parsed_url
