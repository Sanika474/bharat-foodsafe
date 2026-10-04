import hashlib
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from app.core.config import settings

# Bcrypt password and PIN hashing context (12 rounds)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def hash_pin(pin: str) -> str:
    return pwd_context.hash(pin)


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    if not plain_pin or not hashed_pin:
        return False
    return pwd_context.verify(plain_pin, hashed_pin)


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a refresh token string for database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: str | uuid.UUID,
    tenant_id: str | uuid.UUID | None,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    now = utc_now()
    delta = expires_delta or timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES)
    expires_at = now + delta

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id) if tenant_id else None,
        "roles": roles,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def create_refresh_token(
    user_id: str | uuid.UUID,
    family_id: str | uuid.UUID | None = None,
    session_id: str | uuid.UUID | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, uuid.UUID, uuid.UUID, datetime]:
    now = utc_now()
    delta = expires_delta or timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
    expires_at = now + delta

    fam_id = uuid.UUID(str(family_id)) if family_id else uuid.uuid4()
    sess_id = uuid.UUID(str(session_id)) if session_id else uuid.uuid4()

    payload = {
        "sub": str(user_id),
        "family_id": str(fam_id),
        "session_id": str(sess_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, fam_id, sess_id, expires_at


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")
