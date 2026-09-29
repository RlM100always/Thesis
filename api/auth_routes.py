"""Account endpoints: register, login, refresh, logout, and the caller's permissions.

Sign-in is email + password. Access tokens are short-lived; refresh tokens are
longer-lived and rotate on every use. ``User.token_version`` revokes every
outstanding token for a user at once (logout, password change).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import UserView
from .auth import (
    CurrentMembership, CurrentUser, create_access_token, create_refresh_token,
    decode_token_claims,
)
from .config import get_settings
from .database import get_db
from .domain_models import AuditLog, User
from .permissions import permissions_for
from .security import DUMMY_HASH, hash_password, hash_setup_token, verify_password

router = APIRouter(prefix="/api/app/auth")
Db = Annotated[Session, Depends(get_db)]

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# email -> timestamps of recent failed logins. In-process only: enough to slow a
# guessing attack on one server; a shared store replaces it if the API scales out.
_failed_logins: dict[str, list[float]] = {}


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserView


def _token_response(user: User) -> TokenOut:
    settings = get_settings()
    version = int(user.token_version or 0)
    return TokenOut(
        access_token=create_access_token(user.id, version),
        refresh_token=create_refresh_token(user.id, version),
        expires_in=settings.access_token_minutes * 60,
        user=UserView.model_validate(user, from_attributes=True),
    )


def _recent_failures(email: str) -> list[float]:
    window = get_settings().login_lockout_minutes * 60
    cutoff = time.monotonic() - window
    fresh = [stamp for stamp in _failed_logins.get(email, []) if stamp > cutoff]
    if fresh:
        _failed_logins[email] = fresh
    else:
        _failed_logins.pop(email, None)
    return fresh


@router.post("/register", response_model=TokenOut, tags=["app-auth"])
def register(payload: RegisterIn, db: Db):
    if not get_settings().allow_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    email = payload.email.strip().lower()
    user = User(
        email=email, display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
        db.add(AuditLog(actor_user_id=user.id, action="user.registered",
                        entity_type="user", entity_id=user.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    return _token_response(user)


@router.post("/login", response_model=TokenOut, tags=["app-auth"])
def login(payload: LoginIn, db: Db):
    settings = get_settings()
    email = payload.email.strip().lower()
    if len(_recent_failures(email)) >= settings.login_max_failures:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(settings.login_lockout_minutes * 60)},
        )
    user = db.scalar(select(User).where(User.email == email))
    # Always run one scrypt verification so an unknown email and a wrong
    # password take the same time.
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not user.active or not valid:
        _failed_logins.setdefault(email, []).append(time.monotonic())
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _failed_logins.pop(email, None)
    return _token_response(user)


@router.post("/refresh", response_model=TokenOut, tags=["app-auth"])
def refresh(payload: RefreshIn, db: Db):
    claims = decode_token_claims(payload.refresh_token, "refresh")
    user = db.get(User, str(claims["sub"]))
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Unknown or inactive user")
    if int(claims.get("tv", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    return _token_response(user)


class SetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/set-password", response_model=TokenOut, tags=["app-auth"])
def set_password(payload: SetPasswordIn, db: Db):
    """Finish an invite (or an owner-issued reset) with the one-time token.

    The token is single-use and expires. On success the person is signed in.
    """
    user = db.scalar(select(User).where(
        User.setup_token_hash == hash_setup_token(payload.token)))
    expires = user.setup_token_expires_at if user else None
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if user is None or not user.active or expires is None or expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This link is invalid or has expired")
    user.password_hash = hash_password(payload.password)
    user.setup_token_hash = None
    user.setup_token_expires_at = None
    user.token_version = int(user.token_version or 0) + 1  # any older session is void
    db.add(AuditLog(actor_user_id=user.id, action="user.password_set",
                    entity_type="user", entity_id=user.id))
    db.commit()
    return _token_response(user)


@router.post("/change-password", response_model=TokenOut, tags=["app-auth"])
def change_password(payload: ChangePasswordIn, user: CurrentUser, db: Db):
    """Change your own password. Other devices are signed out; this one gets fresh tokens."""
    email = user.email
    if len(_recent_failures(email)) >= get_settings().login_max_failures:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
    # 400, not 401: a 401 makes the client think the session expired and sign out.
    if not verify_password(payload.current_password, user.password_hash):
        _failed_logins.setdefault(email, []).append(time.monotonic())
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    _failed_logins.pop(email, None)
    user.password_hash = hash_password(payload.new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.add(AuditLog(actor_user_id=user.id, action="user.password_changed",
                    entity_type="user", entity_id=user.id))
    db.commit()
    return _token_response(user)


@router.post("/logout", tags=["app-auth"])
def logout(user: CurrentUser, db: Db):
    """Revoke every outstanding access and refresh token for this user."""
    user.token_version = int(user.token_version or 0) + 1
    db.add(user)
    db.add(AuditLog(actor_user_id=user.id, action="user.logged_out",
                    entity_type="user", entity_id=user.id))
    db.commit()
    return {"status": "logged_out"}


@router.get("/permissions", tags=["app-auth"])
def my_permissions(membership: CurrentMembership):
    """The caller's role and permissions in the organization named by X-Organization-ID."""
    return {
        "organization_id": membership.organization_id,
        "role": membership.role,
        "permissions": sorted(permissions_for(membership.role)),
    }
