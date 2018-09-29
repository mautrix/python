from urllib.parse import quote as urllib_quote
import re

from ...api import HTTPAPI


class BaseClientAPI:
    mxid_regex = re.compile("@(.+):(.+)")

    def __init__(self, mxid: str, api: HTTPAPI):
        mxid_parts = self.mxid_regex.match(mxid)
        if not mxid_parts:
            raise ValueError("invalid MXID")
        self.localpart = mxid_parts.group(1)
        self.domain = mxid_parts.group(2)

        self.mxid = mxid
        self.api = api


def quote(*args, **kwargs):
    return urllib_quote(*args, **kwargs, safe="")
