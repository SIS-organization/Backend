"""Erorile aplicației. Sunt transformate în răspunsuri RFC 7807 (problem+json)."""


class AppError(Exception):
    """Eroare de business cu status HTTP și un cod stabil, citibil de frontend."""

    status_code = 400
    title = "Bad Request"
    code = "BAD_REQUEST"

    def __init__(
        self,
        detail: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        title: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        if title is not None:
            self.title = title


class UnauthorizedError(AppError):
    status_code = 401
    title = "Unauthorized"
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    title = "Forbidden"
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    title = "Conflict"
    code = "CONFLICT"


class UnprocessableError(AppError):
    """Cererea este corectă ca format, dar încalcă o regulă de business."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "UNPROCESSABLE"
