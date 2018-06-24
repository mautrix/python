# -*- coding: future_fstrings -*-
from typing import Optional


class MatrixError(Exception):
    """A generic Matrix error. Specific errors will subclass this."""
    pass


class IntentError(MatrixError):
    """An intent execution failure, most likely caused by a `MatrixRequestError`."""

    def __init__(self, message: str, source: Exception):
        super().__init__(message)
        self.source = source


class MatrixRequestError(MatrixError):
    """A standard Matrix request error returned by the homeserver."""

    def __init__(self, code: int = 0, text: str = "", errcode: Optional[str] = None,
                 message: Optional[str] = None):
        super().__init__(f"{code}: {text}")
        self.code = code
        self.text = text
        self.errcode = errcode
        self.message = message

class MatrixResponseError(MatrixError):
    """The response from the homeserver did not fulfill expectations."""

    def __init__(self, message: str):
        super().__init__(message)
