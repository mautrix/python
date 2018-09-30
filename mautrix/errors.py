from typing import Optional


class MatrixError(Exception):
    """A generic Matrix error. Specific errors will subclass this."""
    pass


class MatrixRequestError(MatrixError):
    """A standard Matrix request error returned by the homeserver."""

    def __init__(self, code: int = 0, text: str = "", errcode: Optional[str] = None,
                 message: Optional[str] = None) -> None:
        super().__init__(f"{code}: {text}")
        self.code: int = code
        self.text: str = text
        self.errcode: Optional[str] = errcode
        self.message: Optional[str] = message


class MatrixResponseError(MatrixError):
    """The response from the homeserver did not fulfill expectations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class IntentError(MatrixError):
    """An intent execution failure, most likely caused by a `MatrixRequestError`."""

    def __init__(self, message: str, source: Exception):
        super().__init__(message)
        self.source = source
