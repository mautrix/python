class MatrixError(Exception):
    """A generic Matrix error. Specific errors will subclass this."""
    pass


class MatrixResponseError(MatrixError):
    """The response from the homeserver did not fulfill expectations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class IntentError(MatrixError):
    """An intent execution failure, most likely caused by a `MatrixRequestError`."""
    pass
