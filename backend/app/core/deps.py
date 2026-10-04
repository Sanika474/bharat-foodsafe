from typing import Generator
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.core.security import decode_token
from app.core.tenant import TenantContext
from app.models.identity import User, UserRole

security_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> tuple[User, list[str]]:
    if not credentials or not credentials.credentials:
        raise AppException(
            code="UNAUTHORIZED",
            message="Authentication bearer token missing or invalid.",
            status_code=401,
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError as err:
        raise AppException(
            code="INVALID_TOKEN",
            message=str(err),
            status_code=401,
        )

    if payload.get("type") != "access":
        raise AppException(
            code="INVALID_TOKEN",
            message="Expected access token.",
            status_code=401,
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AppException(
            code="INVALID_TOKEN",
            message="Token payload missing subject identifier.",
            status_code=401,
        )

    user = db.query(User).filter_by(id=user_id_str).first()
    if not user:
        raise AppException(
            code="USER_NOT_FOUND",
            message="User account associated with token not found.",
            status_code=401,
        )

    if user.status != "ACTIVE":
        raise AppException(
            code="ACCOUNT_INACTIVE",
            message=f"User account status is {user.status}.",
            status_code=403,
        )

    # Fetch active roles for user
    user_roles_records = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id, UserRole.revoked_at.is_(None))
        .all()
    )
    roles = [ur.role.name for ur in user_roles_records if ur.role]

    return user, roles


def get_tenant_context(
    user_and_roles: tuple[User, list[str]] = Depends(get_current_user),
) -> TenantContext:
    user, roles = user_and_roles
    return TenantContext(
        user_id=user.id,
        restaurant_id=user.restaurant_id,
        roles=roles,
    )


def require_roles(*allowed_roles: str):
    def role_checker(user_and_roles: tuple[User, list[str]] = Depends(get_current_user)) -> tuple[User, list[str]]:
        user, roles = user_and_roles
        if not any(r in roles for r in allowed_roles):
            raise AppException(
                code="INSUFFICIENT_PERMISSIONS",
                message=f"Operation requires one of the following roles: {list(allowed_roles)}.",
                status_code=403,
            )
        return user, roles

    return role_checker
