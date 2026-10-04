import uuid
from datetime import timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    utc_now,
    verify_password,
    verify_pin,
)
from app.models.identity import User
from app.modules.auth import repository
from app.modules.auth.schema import LoginRequest, TokenResponseData, UserSummary


def login_user(db: Session, req: LoginRequest, client_ip: str = "127.0.0.1") -> TokenResponseData:
    # Enforce rate limit (5 attempts per minute)
    rate_key = f"login:{req.phone or req.email or client_ip}"
    check_rate_limit(rate_key, limit=settings.RATE_LIMIT_LOGIN_PER_MINUTE)

    user: User | None = None

    if req.phone and req.pin:
        user = repository.get_user_by_phone(db, req.phone)
        if not user or not user.pin_hash or not verify_pin(req.pin, user.pin_hash):
            raise AppException(
                code="INVALID_CREDENTIALS",
                message="Invalid phone number or PIN.",
                status_code=401,
            )
    elif req.email and req.password:
        user = repository.get_user_by_email(db, req.email)
        if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
            raise AppException(
                code="INVALID_CREDENTIALS",
                message="Invalid email address or password.",
                status_code=401,
            )
    else:
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="Credentials missing.",
            status_code=400,
        )

    if user.status != "ACTIVE":
        raise AppException(
            code="ACCOUNT_SUSPENDED" if user.status == "SUSPENDED" else "ACCOUNT_DISABLED",
            message=f"User account status is {user.status}. Access denied.",
            status_code=403,
        )

    # Fetch user roles
    roles = repository.get_user_roles(db, user.id)

    # Update last login timestamp
    repository.update_user_last_login(db, user.id)

    # Issue access and refresh tokens
    access_token_str, _ = create_access_token(
        user_id=user.id,
        tenant_id=user.restaurant_id,
        roles=roles,
    )

    refresh_token_str, family_id, session_id, expires_at = create_refresh_token(
        user_id=user.id,
    )

    # Persist session refresh token hash in DB
    ref_hash = hash_token(refresh_token_str)
    repository.create_auth_session(
        db=db,
        user_id=user.id,
        refresh_token_hash=ref_hash,
        token_family_id=family_id,
        session_id=session_id,
        issued_at=utc_now(),
        expires_at=expires_at,
    )

    db.commit()

    return TokenResponseData(
        access_token=access_token_str,
        refresh_token=refresh_token_str,
        token_type="bearer",
        expires_in_seconds=settings.JWT_ACCESS_TTL_MINUTES * 60,
        user=UserSummary(
            id=str(user.id),
            name=user.name,
            restaurant_id=str(user.restaurant_id) if user.restaurant_id else None,
            roles=roles,
        ),
    )


def refresh_user_tokens(db: Session, refresh_token_str: str) -> TokenResponseData:
    if not refresh_token_str:
        raise AppException(
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token is required.",
            status_code=401,
        )

    try:
        payload = decode_token(refresh_token_str)
    except ValueError as err:
        raise AppException(
            code="INVALID_REFRESH_TOKEN",
            message=f"Invalid refresh token: {str(err)}",
            status_code=401,
        )

    if payload.get("type") != "refresh":
        raise AppException(
            code="INVALID_REFRESH_TOKEN",
            message="Provided token is not a refresh token.",
            status_code=401,
        )

    ref_hash = hash_token(refresh_token_str)
    session = repository.get_auth_session_by_hash(db, ref_hash)

    if not session:
        raise AppException(
            code="INVALID_REFRESH_TOKEN",
            message="Refresh session record not found.",
            status_code=401,
        )

    # REUSE DETECTION: If session is already revoked or replaced, revoke entire token family
    if session.revoked_at is not None or session.replaced_by_session_id is not None:
        repository.revoke_token_family(db, session.token_family_id)
        db.commit()
        raise AppException(
            code="TOKEN_FAMILY_REVOKED",
            message="Security alert: Refresh token reuse detected. All active sessions in family revoked.",
            status_code=401,
        )

    # Check expiry
    now = utc_now()
    sess_exp = session.expires_at
    if sess_exp.tzinfo is None:
        sess_exp = sess_exp.replace(tzinfo=timezone.utc)

    if sess_exp < now:
        session.revoked_at = now
        db.commit()
        raise AppException(
            code="EXPIRED_REFRESH_TOKEN",
            message="Refresh token has expired. Please login again.",
            status_code=401,
        )

    user = session.user
    if not user or user.status != "ACTIVE":
        repository.revoke_token_family(db, session.token_family_id)
        db.commit()
        raise AppException(
            code="ACCOUNT_SUSPENDED",
            message="Associated user account is no longer active.",
            status_code=403,
        )

    roles = repository.get_user_roles(db, user.id)

    # Rotate refresh token: new token shares family_id
    new_access_token_str, _ = create_access_token(
        user_id=user.id,
        tenant_id=user.restaurant_id,
        roles=roles,
    )

    new_refresh_token_str, family_id, new_session_id, expires_at = create_refresh_token(
        user_id=user.id,
        family_id=session.token_family_id,
    )

    new_ref_hash = hash_token(new_refresh_token_str)

    # Create new session record
    repository.create_auth_session(
        db=db,
        user_id=user.id,
        refresh_token_hash=new_ref_hash,
        token_family_id=family_id,
        session_id=new_session_id,
        issued_at=now,
        expires_at=expires_at,
    )

    # Mark old session revoked and replaced by new session
    repository.revoke_and_replace_session(db, session, new_session_id)

    db.commit()

    return TokenResponseData(
        access_token=new_access_token_str,
        refresh_token=new_refresh_token_str,
        token_type="bearer",
        expires_in_seconds=settings.JWT_ACCESS_TTL_MINUTES * 60,
        user=UserSummary(
            id=str(user.id),
            name=user.name,
            restaurant_id=str(user.restaurant_id) if user.restaurant_id else None,
            roles=roles,
        ),
    )


def logout_user(db: Session, refresh_token_str: str | None) -> None:
    if not refresh_token_str:
        return
    ref_hash = hash_token(refresh_token_str)
    session = repository.get_auth_session_by_hash(db, ref_hash)
    if session and session.revoked_at is None:
        session.revoked_at = utc_now()
        db.commit()


def get_user_profile(user: User, roles: list[str]) -> UserSummary:
    return UserSummary(
        id=str(user.id),
        name=user.name,
        restaurant_id=str(user.restaurant_id) if user.restaurant_id else None,
        roles=roles,
    )
