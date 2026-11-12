"""Punctul de intrare al aplicației FastAPI."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.routers import booking_router, facility_router, health_router

PROBLEM_JSON = "application/problem+json"


def _problem(
    request: Request,
    status_code: int,
    title: str,
    code: str,
    detail: str,
    errors: list[dict] | None = None,
) -> JSONResponse:
    """Răspuns de eroare în format RFC 7807."""
    body: dict = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "code": code,
        "detail": detail,
        "instance": request.url.path,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status_code, media_type=PROBLEM_JSON)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Rezervări pentru facilitățile sportive USV.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _problem(request, exc.status_code, exc.title, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return _problem(
            request,
            400,
            "Bad Request",
            "VALIDATION_ERROR",
            "Datele trimise nu sunt valide.",
            errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        title = HTTPStatus(exc.status_code).phrase
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return _problem(request, exc.status_code, title, code, str(exc.detail))

    for router_module in (health_router, facility_router, booking_router):
        app.include_router(router_module.router, prefix="/v1")

    return app


app = create_app()
