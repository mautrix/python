# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


class MatrixError(Exception):
    """A generic Matrix error. Specific errors will subclass this."""

    pass


class MatrixConnectionError(MatrixError):
    pass


class MatrixResponseError(MatrixError):
    """The response from the homeserver did not fulfill expectations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class IntentError(MatrixError):
    """An intent execution failure, most likely caused by a `MatrixRequestError`."""

    pass
