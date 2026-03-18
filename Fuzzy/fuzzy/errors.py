from __future__ import annotations


class FrameworkError(Exception):
    def __init__(
        self,
        *,
        operation: str,
        category: str,
        message: str,
        attempt_count: int,
        final_validation_category: str | None = None,
        cause: Exception | None = None,
        trace=None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.category = category
        self.message = message
        self.attempt_count = attempt_count
        self.final_validation_category = final_validation_category
        self.trace = trace
        self.__cause__ = cause

    def __str__(self) -> str:
        return self.message


class ProviderError(Exception):
    def __init__(self, category: str, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.__cause__ = cause


class SchemaValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
