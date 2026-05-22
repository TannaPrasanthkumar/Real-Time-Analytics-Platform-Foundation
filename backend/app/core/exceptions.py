from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)


class AppException(Exception):
    """Base application exception for custom business errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)


class AuthenticationException(AppException):
    """Raised when authentication credentials fail or are missing."""

    def __init__(self, message: str = "Authentication credentials failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_FAILED",
            details=details,
        )


class AuthorizationException(AppException):
    """Raised when role permission checks fail."""

    def __init__(self, message: str = "Operation unauthorized for current role", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_FAILED",
            details=details,
        )


class NotFoundException(AppException):
    """Raised when an object or resource is not found."""

    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            details=details,
        )


class ValidationException(AppException):
    """Raised when business validation rules fail."""

    def __init__(self, message: str = "Validation failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_FAILED",
            details=details,
        )


class RateLimitException(AppException):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
        )


# Class aliases to align with imports across endpoints, routers, and guards
UnauthorizedException = AuthenticationException
ForbiddenException = AuthorizationException
BadRequestException = ValidationException


def register_exception_handlers(app: FastAPI) -> None:
    """Registers global exception handlers for the FastAPI application.
    
    Transforms arbitrary Exceptions and Custom AppExceptions into structured,
    type-safe JSON responses including correlation IDs.
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "N/A")
        
        # Log custom exceptions at appropriate levels
        log_payload = {
            "path": request.url.path,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "correlation_id": correlation_id,
        }
        
        if exc.status_code >= 500:
            logger.error("Internal application exception encountered", **log_payload)
        else:
            logger.warning("Business exception encountered", **log_payload)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    "correlation_id": correlation_id,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "N/A")
        
        # Clean Pydantic validation error lists
        formatted_errors = []
        for error in exc.errors():
            formatted_errors.append({
                "field": " -> ".join([str(loc) for loc in error["loc"][1:]]),
                "type": error["type"],
                "message": error["msg"],
            })

        logger.warning(
            "Request validation failed",
            path=request.url.path,
            errors=formatted_errors,
            correlation_id=correlation_id,
        )

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "REQUEST_VALIDATION_FAILED",
                    "message": "Input validation failed on incoming request parameters.",
                    "details": formatted_errors,
                    "correlation_id": correlation_id,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "N/A")
        
        logger.exception(
            "Unhandled system exception caught by global boundary",
            path=request.url.path,
            error=str(exc),
            correlation_id=correlation_id,
        )

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected critical error occurred. Please contact system support.",
                    "details": str(exc) if app.debug else None,
                    "correlation_id": correlation_id,
                },
            },
        )
