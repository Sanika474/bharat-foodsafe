import uuid
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.rate_limit import check_rate_limit
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.uploads import service
from app.modules.uploads.schema import PresignRequest

router = APIRouter(prefix="/uploads", tags=["Uploads & Evidence"])


@router.post(
    "/presign",
    summary="Request presigned object-storage upload URL for evidence file",
)
def presign_upload_endpoint(
    request: Request,
    req: PresignRequest,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    # Enforce rate limit (20 presign requests per 60s window)
    rate_key = f"upload_presign:{tenant_ctx.user_id}"
    check_rate_limit(rate_key, limit=20)

    base_url = str(request.base_url)
    result = service.request_presigned_upload(db, tenant_ctx, req, base_url=base_url)

    return success_response(
        data=result.model_dump(),
        status_code=status.HTTP_201_CREATED,
    )


@router.put(
    "/raw/{storage_key:path}",
    summary="Upload raw binary payload (Local storage mode)",
)
async def raw_binary_upload_endpoint(
    storage_key: str,
    request: Request,
):
    body = await request.body()
    service.save_raw_binary_content(storage_key, body)
    return success_response(
        data={"message": "Raw binary payload stored successfully.", "bytes_received": len(body)},
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{evidence_file_id}/confirm",
    summary="Confirm evidence file upload and perform binary magic-byte validation & SHA-256 calculation",
)
def confirm_upload_endpoint(
    evidence_file_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    result = service.confirm_evidence_upload(db, tenant_ctx, evidence_file_id)
    return success_response(
        data=result.model_dump(),
        meta={"message": "Evidence upload validated and confirmed."},
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/{evidence_file_id}",
    summary="Get evidence file metadata and status",
)
def get_upload_metadata_endpoint(
    evidence_file_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    result = service.get_evidence_file_details(db, tenant_ctx, evidence_file_id)
    return success_response(data=result.model_dump())


@router.get(
    "/{evidence_file_id}/file",
    summary="Download/preview evidence binary file",
)
def get_upload_binary_file_endpoint(
    evidence_file_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    content, mime_type, filename = service.get_evidence_file_binary(db, tenant_ctx, evidence_file_id)
    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
