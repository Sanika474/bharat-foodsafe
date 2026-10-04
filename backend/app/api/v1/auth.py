from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.identity import User
from app.modules.auth import service
from app.modules.auth.schema import LoginRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "127.0.0.1"
    token_data = service.login_user(db, body, client_ip=client_ip)

    # Set HTTP-only refresh cookie
    response.set_cookie(
        key="refresh_token",
        value=token_data.refresh_token,
        httponly=True,
        secure=False,  # True in prod HTTPS
        samesite="lax",
        max_age=7 * 24 * 3600,
    )

    return success_response(data=token_data.model_dump())


@router.post("/refresh")
def refresh_tokens(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    cookie_refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
    x_refresh_token: str | None = Header(default=None, alias="X-Refresh-Token"),
    db: Session = Depends(get_db),
):
    # Extract refresh token from body, cookie, or header
    refresh_token = None
    if body and body.refresh_token:
        refresh_token = body.refresh_token
    elif cookie_refresh_token:
        refresh_token = cookie_refresh_token
    elif x_refresh_token:
        refresh_token = x_refresh_token

    token_data = service.refresh_user_tokens(db, refresh_token or "")

    # Update HTTP-only cookie with rotated refresh token
    response.set_cookie(
        key="refresh_token",
        value=token_data.refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )

    return success_response(data=token_data.model_dump())


@router.post("/logout")
def logout(
    response: Response,
    body: RefreshRequest | None = None,
    cookie_refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
    db: Session = Depends(get_db),
):
    refresh_token = (body and body.refresh_token) or cookie_refresh_token
    service.logout_user(db, refresh_token)

    response.delete_cookie(key="refresh_token")
    return success_response(data={"message": "Logged out successfully."})


@router.get("/me")
def get_me(
    current_user_and_roles: tuple[User, list[str]] = Depends(get_current_user),
):
    user, roles = current_user_and_roles
    profile = service.get_user_profile(user, roles)
    return success_response(data=profile.model_dump())
