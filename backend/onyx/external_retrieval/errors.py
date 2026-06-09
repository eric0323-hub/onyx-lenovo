class ExternalRetrievalError(Exception):
    """Base error for external retrieval configuration and runtime failures."""

    error_code = "external_retrieval_error"


class ExternalRetrievalConfigurationError(ExternalRetrievalError):
    error_code = "configuration_error"


class ExternalRetrievalResponseError(ExternalRetrievalError):
    error_code = "response_error"


class ExternalRetrievalRequestError(ExternalRetrievalError):
    error_code = "request_error"

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code
