import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.responses import error_response

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Bharat FoodSafe Digital Compliance Platform API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
app.include_router(api_v1_router)


# Custom Exception Handlers for Standard Error Envelope
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    return error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
        request_id=req_id,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    formatted_details = []
    for error in exc.errors():
        loc_str = " -> ".join(str(x) for x in error.get("loc", []))
        formatted_details.append({
            "field": loc_str,
            "issue": error.get("msg", "Validation error"),
        })

    return error_response(
        code="VALIDATION_ERROR",
        message="Request payload validation failed.",
        details=formatted_details,
        status_code=422,
        request_id=req_id,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
    }
    error_code = code_map.get(exc.status_code, "HTTP_ERROR")
    return error_response(
        code=error_code,
        message=str(exc.detail),
        status_code=exc.status_code,
        request_id=req_id,
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/ready", tags=["Health"])
def readiness_check():
    return {
        "status": "ready",
        "database": "connected_mock",
    }
