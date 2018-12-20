# Copyright (c) 2018 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from .base import MatrixError, MatrixConnectionError, MatrixResponseError, IntentError
from .request import (MatrixRequestError, MatrixUnknownRequestError, MatrixStandardRequestError,
                      standard_error, make_request_error,
                      MForbidden, MatrixInvalidToken, MUnknownToken, MMissingToken,
                      MatrixBadRequest, MatrixBadContent, MBadJSON, MNotJSON, MNotFound,
                      MLimitExceeded, MUnknown, MUnrecognized, MUnauthorized, MUserInUse,
                      MInvalidUsername, MRoomInUse, MInvalidRoomState, MUnsupportedRoomVersion,
                      MIncompatibleRoomVersion, MBadState, MGuestAccessForbidden, MCaptchaNeeded,
                      MCaptchaInvalid, MMissingParam, MInvalidParam, MTooLarge, MExclusive)
