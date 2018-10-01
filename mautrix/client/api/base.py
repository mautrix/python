from typing import Pattern
from urllib.parse import quote as urllib_quote
import re

from ...api import HTTPAPI
from .types import UserID


class BaseClientAPI:
    """
    BaseClientAPI is the base class for :ClientAPI:. This is separate from the main ClientAPI class
    so that the ClientAPI methods can be split into multiple classes (that inherit this class). All
    those section-specific method classes are inherited by the main ClientAPI class to create the
    full class.
    """
    mxid_regex: Pattern = re.compile("@(.+):(.+)")

    localpart: str
    domain: str
    mxid: UserID
    api: HTTPAPI

    def __init__(self, mxid: UserID, api: HTTPAPI) -> None:
        """
        Initialize a ClientAPI.

        Args:
            mxid: The Matrix ID of the user. This is used for things like setting profile metadata.
                Additionally, the homeserver domain is extracted from this string and used for
                setting aliases and such. This can be changed later using `set_mxid`.
            api: The HTTPAPI instance to use.
        """
        self.set_mxid(mxid)
        self.api = api

    def set_mxid(self, mxid: UserID) -> None:
        """
        Update the Matrix user ID used by this ClientAPI.

        Args:
            mxid: The new Matrix user ID.
        """
        mxid_parts = self.mxid_regex.match(mxid)
        if not mxid_parts:
            raise ValueError("invalid MXID")
        self.localpart = mxid_parts.group(1)
        self.domain = mxid_parts.group(2)

        self.mxid = mxid


def quote(string: str) -> str:
    return urllib_quote(string, safe="")
