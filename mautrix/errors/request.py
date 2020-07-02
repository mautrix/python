# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, Type, Callable

from .base import MatrixError


class MatrixRequestError(MatrixError):
    """An error that was returned by the homeserver."""
    http_status: int
    message: Optional[str]
    errcode: str


class MatrixUnknownRequestError(MatrixRequestError):
    """An unknown error type returned by the homeserver."""

    def __init__(self, http_status: int = 0, text: str = "", errcode: Optional[str] = None,
                 message: Optional[str] = None) -> None:
        super().__init__(f"{http_status}: {text}")
        self.http_status: int = http_status
        self.text: str = text
        self.errcode: Optional[str] = errcode
        self.message: Optional[str] = message


class MatrixStandardRequestError(MatrixRequestError):
    """A standard error type returned by the homeserver."""
    errcode: str = None

    def __init__(self, http_status: int, message: str = "") -> None:
        super().__init__(message)
        self.http_status: int = http_status
        self.message: str = message


MxSRE = Type[MatrixStandardRequestError]
ec_map: Dict[str, MxSRE] = {}


def standard_error(code: str) -> Callable[[MxSRE], MxSRE]:
    def decorator(cls: MxSRE) -> MxSRE:
        cls.errcode = code
        ec_map[code] = cls
        return cls

    return decorator


def make_request_error(http_status: int, text: str, errcode: str,
                       message: str) -> MatrixRequestError:
    """
    Determine the correct exception class for the error code and create an instance of that class
    with the given values.

    Args:
        http_status: The HTTP status code.
        text: The raw response text.
        errcode: The errcode field in the response JSON.
        message: The error field in the response JSON.
    """
    try:
        ec_class = ec_map[errcode]
        return ec_class(http_status, message)
    except KeyError:
        return MatrixUnknownRequestError(http_status, text, errcode, message)


# Standard error codes from https://matrix.org/docs/spec/client_server/r0.4.0.html#api-standards
# Additionally some combining superclasses for some of the error codes

@standard_error("M_FORBIDDEN")
class MForbidden(MatrixStandardRequestError):
    pass


@standard_error("M_USER_DEACTIVATED")
class MUserDeactivated(MForbidden):
    pass


class MatrixInvalidToken(MatrixStandardRequestError):
    pass


@standard_error("M_UNKNOWN_TOKEN")
class MUnknownToken(MatrixInvalidToken):
    pass


@standard_error("M_MISSING_TOKEN")
class MMissingToken(MatrixInvalidToken):
    pass


class MatrixBadRequest(MatrixStandardRequestError):
    pass


class MatrixBadContent(MatrixBadRequest):
    pass


@standard_error("M_BAD_JSON")
class MBadJSON(MatrixBadContent):
    pass


@standard_error("M_NOT_JSON")
class MNotJSON(MatrixBadContent):
    pass


@standard_error("M_NOT_FOUND")
class MNotFound(MatrixStandardRequestError):
    pass


@standard_error("M_LIMIT_EXCEEDED")
class MLimitExceeded(MatrixStandardRequestError):
    pass


@standard_error("M_UNKNOWN")
class MUnknown(MatrixStandardRequestError):
    pass


@standard_error("M_UNRECOGNIZED")
class MUnrecognized(MatrixStandardRequestError):
    pass


@standard_error("M_UNAUTHORIZED")
class MUnauthorized(MatrixStandardRequestError):
    pass


@standard_error("M_USER_IN_USE")
class MUserInUse(MatrixStandardRequestError):
    pass


@standard_error("M_INVALID_USERNAME")
class MInvalidUsername(MatrixStandardRequestError):
    pass


@standard_error("M_ROOM_IN_USE")
class MRoomInUse(MatrixStandardRequestError):
    pass


@standard_error("M_INVALID_ROOM_STATE")
class MInvalidRoomState(MatrixStandardRequestError):
    pass


# TODO THREEPID_ errors


@standard_error("M_UNSUPPORTED_ROOM_VERSION")
class MUnsupportedRoomVersion(MatrixStandardRequestError):
    pass


@standard_error("M_INCOMPATIBLE_ROOM_VERSION")
class MIncompatibleRoomVersion(MatrixStandardRequestError):
    pass


@standard_error("M_BAD_STATE")
class MBadState(MatrixStandardRequestError):
    pass


@standard_error("M_GUEST_ACCESS_FORBIDDEN")
class MGuestAccessForbidden(MatrixStandardRequestError):
    pass


@standard_error("M_CAPTCHA_NEEDED")
class MCaptchaNeeded(MatrixStandardRequestError):
    pass


@standard_error("M_CAPTCHA_INVALID")
class MCaptchaInvalid(MatrixStandardRequestError):
    pass


@standard_error("M_MISSING_PARAM")
class MMissingParam(MatrixBadRequest):
    pass


@standard_error("M_INVALID_PARAM")
class MInvalidParam(MatrixBadRequest):
    pass


@standard_error("M_TOO_LARGE")
class MTooLarge(MatrixBadRequest):
    pass


@standard_error("M_EXCLUSIVE")
class MExclusive(MatrixStandardRequestError):
    pass
