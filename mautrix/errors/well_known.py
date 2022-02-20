# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .base import MatrixResponseError


class WellKnownError(MatrixResponseError):
    """
    An error that occurred during server discovery.

    https://matrix.org/docs/spec/client_server/latest#get-well-known-matrix-client
    """

    pass


class WellKnownUnexpectedStatus(WellKnownError):
    def __init__(self, status: int) -> None:
        super().__init__(f"Unexpected status code {status} when fetching .well-known file")
        self.status = status


class WellKnownNotJSON(WellKnownError):
    def __init__(self) -> None:
        super().__init__(".well-known response was not JSON")


class WellKnownMissingHomeserver(WellKnownError):
    def __init__(self) -> None:
        super().__init__("No homeserver found in .well-known response")


class WellKnownNotURL(WellKnownError):
    def __init__(self) -> None:
        super().__init__("Homeserver base URL in .well-known response was not a valid URL")


class WellKnownUnsupportedScheme(WellKnownError):
    def __init__(self, scheme: str) -> None:
        super().__init__(f"URL in .well-known response has unsupported scheme {scheme}")


class WellKnownInvalidVersionsResponse(WellKnownError):
    def __init__(self) -> None:
        super().__init__(
            "URL in .well-known response didn't respond to versions endpoint properly"
        )
