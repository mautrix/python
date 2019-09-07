# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Tuple
import warnings
import asyncio
import logging

from ...api import HTTPAPI
from .types import UserID


class BaseClientAPI:
    """
    BaseClientAPI is the base class for :class:`ClientAPI`. This is separate from the main
    ClientAPI class so that the ClientAPI methods can be split into multiple classes (that
    inherit this class).All those section-specific method classes are inherited by the main
    ClientAPI class to create the full class.
    """

    localpart: str
    domain: str
    mxid: UserID
    api: HTTPAPI
    loop: asyncio.AbstractEventLoop
    log: logging.Logger

    def __init__(self, mxid: UserID, api: HTTPAPI = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None, *args, **kwargs) -> None:
        """
        Initialize a ClientAPI. You must either provide the

        Args:
            mxid: The Matrix ID of the user. This is used for things like setting profile metadata.
                Additionally, the homeserver domain is extracted from this string and used for
                setting aliases and such. This can be changed later using `set_mxid`.
            api: The :class:`HTTPAPI` instance to use. You can also pass the ``args`` and ``kwargs``
                to create a HTTPAPI instance rather than creating the instance yourself.``
        """
        self.set_mxid(mxid)
        if loop:
            kwargs["loop"] = loop
        self.api = api or HTTPAPI(*args, **kwargs)
        self.loop = self.api.loop
        self.log = self.api.log

    @classmethod
    def parse_mxid(cls, mxid: UserID) -> Tuple[str, str]:
        warnings.warn("parse_mxid is deprecated, use parse_user_id instead",
                      category=DeprecationWarning)
        return cls.parse_user_id(mxid)

    @classmethod
    def parse_user_id(cls, mxid: UserID) -> Tuple[str, str]:
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
        return mxid[1:sep], mxid[sep + 1:]

    def set_mxid(self, mxid: UserID) -> None:
        """
        Update the Matrix user ID used by this ClientAPI.

        Args:
            mxid: The new Matrix user ID.
        """
        self.localpart, self.domain = self.parse_user_id(mxid)
        self.mxid = mxid
