# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Pattern, Optional, Tuple
import asyncio
import logging
import re

from ...api import HTTPAPI
from .types import UserID


class BaseClientAPI:
    """
    BaseClientAPI is the base class for :class:`ClientAPI`. This is separate from the main
    ClientAPI class so that the ClientAPI methods can be split into multiple classes (that
    inherit this class).All those section-specific method classes are inherited by the main
    ClientAPI class to create the full class.
    """
    mxid_regex: Pattern = re.compile("@(.+):(.+)")

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
        self.loop = loop or api.loop or asyncio.get_event_loop()
        kwargs["loop"] = self.loop
        self.api = api or HTTPAPI(*args, **kwargs)
        self.log = self.api.log

    @classmethod
    def parse_mxid(cls, mxid: UserID) -> Tuple[str, str]:
        """
        Parse the localpart and server name from a Matrix user ID.

        Args:
            mxid: The Matrix user ID.

        Returns:
            A tuple of (localpart, server_name)
        """
        mxid_parts = cls.mxid_regex.match(mxid)
        if not mxid_parts:
            raise ValueError("invalid MXID")
        return mxid_parts.group(1), mxid_parts.group(2)

    def set_mxid(self, mxid: UserID) -> None:
        """
        Update the Matrix user ID used by this ClientAPI.

        Args:
            mxid: The new Matrix user ID.
        """
        self.localpart, self.domain = self.parse_mxid(mxid)
        self.mxid = mxid
