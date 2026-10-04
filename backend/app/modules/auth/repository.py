import uuid
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.identity import AuthSession, User, UserRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_user_by_phone(db: Session, phone: str) -> User | None:
    return db.query(User).filter(User.phone == phone).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()


def get_user_roles(db: Session, user_id: uuid.UUID) -> list[str]:
    user_roles_records = (
        db.query(UserRole)
        .filter(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))
        .all()
    )
    return [ur.role.name for ur in user_roles_records if ur.role]


def update_user_last_login(db: Session, user_id: uuid.UUID) -> None:
    user = db.query(User).filter_by(id=user_id).first()
    if user:
        user.last_login_at = utc_now()
        db.flush()


def create_auth_session(
    db: Session,
    user_id: uuid.UUID,
    refresh_token_hash: str,
    token_family_id: uuid.UUID,
    session_id: uuid.UUID,
    issued_at: datetime,
    expires_at: datetime,
    device_id: uuid.UUID | None = None,
) -> AuthSession:
    session = AuthSession(
        id=session_id,
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        token_family_id=token_family_id,
        device_id=device_id,
        issued_at=issued_at,
        expires_at=expires_at,
        revoked_at=None,
        last_used_at=issued_at,
        replaced_by_session_id=None,
    )
    db.add(session)
    db.flush()
    return session


def get_auth_session_by_hash(db: Session, refresh_token_hash: str) -> AuthSession | None:
    return db.query(AuthSession).filter_by(refresh_token_hash=refresh_token_hash).first()


def revoke_token_family(db: Session, token_family_id: uuid.UUID) -> int:
    """Revokes all active sessions sharing the specified token_family_id.
    Triggered upon detection of refresh token reuse.
    """
    now = utc_now()
    count = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_family_id == token_family_id,
            AuthSession.revoked_at.is_(None),
        )
        .update({AuthSession.revoked_at: now}, synchronize_session=False)
    )
    db.flush()
    return count


def revoke_and_replace_session(
    db: Session,
    old_session: AuthSession,
    new_session_id: uuid.UUID,
) -> None:
    now = utc_now()
    old_session.revoked_at = now
    old_session.replaced_by_session_id = new_session_id
    db.flush()
