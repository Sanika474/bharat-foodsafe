import uuid
from typing import Any
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    meta: dict[str, Any] | None = None,
    request_id: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    meta_dict = meta or {}
    meta_dict.setdefault("request_id", req_id)
    if "pagination" not in meta_dict:
        meta_dict["pagination"] = None

    payload = {
        "success": True,
        "data": data,
        "meta": meta_dict,
    }
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


def error_response(
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    status_code: int = 400,
    request_id: str | None = None,
) -> JSONResponse:
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        },
        "meta": {
            "request_id": req_id,
        },
    }
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))
