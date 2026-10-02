"""Account endpoints: register, login, refresh, logout, and the caller's permissions.

Sign-in is email + password. Access tokens are short-lived; refresh tokens are
longer-lived and rotate on every use. ``User.token_version`` revokes every
outstanding token for a user at once (logout, password change).
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import json

from .app_schemas import UserView
from .auth import (
    CurrentMembership, CurrentUser, create_access_token, create_mfa_challenge_token,
    create_refresh_token, decode_token_claims,
)
from .config import get_settings
from .database import get_db
from .domain_models import AuditLog, User, UserSession
from .permissions import permissions_for
from .security import DUMMY_HASH, hash_password, hash_setup_token, verify_password
from .totp import new_recovery_codes, new_totp_secret, provisioning_uri, verify_totp

router = APIRouter(prefix="/api/app/auth")
Db = Annotated[Session, Depends(get_db)]

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
RESET_LINK_HOURS = 1


def _deliver_reset_link(user: User, raw_token: str) -> None:
    """Hand the raw reset token to the person -- never to the HTTP caller.

    No live email/SMS provider is wired for this flow yet (CLAUDE.md: no real
    provider credential without a legal merchant/sender account), so this is
    the integration seam: swap this one function for a real send and nothing
    about the request/response contract above it changes. Tests monkeypatch
    it to capture the token the way a real inbox would receive it.
    """
    import logging

    logging.getLogger("api.auth").info(
        "Password reset link for %s: %s/#/reset-password?token=%s",
        user.email, get_settings().public_app_url, raw_token,
    )

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


class MfaVerifyIn(BaseModel):
    mfa_token: str
    code: str = Field(min_length=4, max_length=12)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserView


def _device_label(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("user-agent")
    return ua[:200] if ua else None


def _client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def _new_session(db: Session, user: User, request: Request | None) -> UserSession:
    """Start a new rotating-refresh-token family for one device/browser."""
    settings = get_settings()
    session = UserSession(
        user_id=user.id,
        current_jti_hash=hash_setup_token(secrets.token_urlsafe(32)),  # placeholder, set below
        device_label=_device_label(request),
        ip_address=_client_ip(request),
        last_used_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
    )
    db.add(session)
    db.flush()
    return session


def _token_response(user: User, db: Session, request: Request | None = None) -> TokenOut:
    settings = get_settings()
    version = int(user.token_version or 0)
    session = _new_session(db, user, request)
    jti = secrets.token_urlsafe(32)
    session.current_jti_hash = hash_setup_token(jti)
    db.commit()
    return TokenOut(
        access_token=create_access_token(user.id, version, sid=session.id),
        refresh_token=create_refresh_token(user.id, version, sid=session.id, jti=jti),
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
def register(payload: RegisterIn, db: Db, request: Request):
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
    return _token_response(user, db, request)


class MfaRequiredOut(BaseModel):
    mfa_required: bool = True
    mfa_token: str


@router.post("/login", response_model=TokenOut | MfaRequiredOut, tags=["app-auth"])
def login(payload: LoginIn, db: Db, request: Request):
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
    if user.mfa_enabled:
        # Password is correct, but tokens are not issued yet -- AUTH-003.
        return MfaRequiredOut(mfa_token=create_mfa_challenge_token(user.id, int(user.token_version or 0)))
    return _token_response(user, db, request)


@router.post("/mfa/verify", response_model=TokenOut, tags=["app-auth"])
def verify_mfa(payload: MfaVerifyIn, db: Db, request: Request):
    """Second step of login for an MFA-enabled account: TOTP code or a recovery code."""
    claims = decode_token_claims(payload.mfa_token, "mfa")
    user = db.get(User, str(claims["sub"]))
    if user is None or not user.active or not user.mfa_enabled:
        raise HTTPException(status_code=401, detail="This MFA challenge is no longer valid")
    if int(claims.get("tv", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="This MFA challenge is no longer valid")
    if len(_recent_failures(f"mfa:{user.id}")) >= get_settings().login_max_failures:
        raise HTTPException(status_code=429, detail="Too many failed codes. Try again later.")
    code = payload.code.strip()
    ok = bool(user.mfa_totp_secret) and verify_totp(user.mfa_totp_secret, code)
    if not ok:
        codes = json.loads(user.mfa_recovery_codes_json or "[]")
        digest = hash_setup_token(code)
        if digest in codes:
            ok = True
            codes.remove(digest)  # single use
            user.mfa_recovery_codes_json = json.dumps(codes)
            db.add(AuditLog(actor_user_id=user.id, action="user.mfa_recovery_code_used",
                            entity_type="user", entity_id=user.id))
    if not ok:
        _failed_logins.setdefault(f"mfa:{user.id}", []).append(time.monotonic())
        raise HTTPException(status_code=401, detail="Invalid code")
    _failed_logins.pop(f"mfa:{user.id}", None)
    db.commit()
    return _token_response(user, db, request)


@router.post("/refresh", response_model=TokenOut, tags=["app-auth"])
def refresh(payload: RefreshIn, db: Db, request: Request):
    claims = decode_token_claims(payload.refresh_token, "refresh")
    user = db.get(User, str(claims["sub"]))
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Unknown or inactive user")
    if int(claims.get("tv", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    sid, jti = claims.get("sid"), claims.get("jti")
    if not sid or not jti:
        # Token predates session tracking -- no family to rotate or check for reuse.
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    session = db.get(UserSession, str(sid))
    now = datetime.now(timezone.utc)
    expires_at = session.expires_at if session else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if session is None or session.user_id != user.id or session.revoked_at is not None or (
        expires_at is not None and expires_at < now
    ):
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    if session.current_jti_hash != hash_setup_token(str(jti)):
        # This refresh token was already rotated away -- it is either stolen
        # or replayed. Revoke the whole family rather than trust either caller.
        session.revoked_at = now
        session.revoked_reason = "refresh_token_reuse_detected"
        db.add(AuditLog(actor_user_id=user.id, action="user.session_reuse_detected",
                        entity_type="user_session", entity_id=session.id))
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    new_jti = secrets.token_urlsafe(32)
    session.current_jti_hash = hash_setup_token(new_jti)
    session.last_used_at = now
    session.ip_address = _client_ip(request) or session.ip_address
    db.commit()
    settings = get_settings()
    version = int(user.token_version or 0)
    return TokenOut(
        access_token=create_access_token(user.id, version, sid=session.id),
        refresh_token=create_refresh_token(user.id, version, sid=session.id, jti=new_jti),
        expires_in=settings.access_token_minutes * 60,
        user=UserView.model_validate(user, from_attributes=True),
    )


class ForgotPasswordIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)


_GENERIC_RECOVERY_RESPONSE = {
    "status": "ok",
    "detail": "If that account exists, a reset link has been sent.",
}


@router.post("/forgot-password", tags=["app-auth"])
def forgot_password(payload: ForgotPasswordIn, db: Db):
    """Start a self-service password reset. AUTH-009: never reveal whether the account exists."""
    email = payload.email.strip().lower()
    if len(_recent_failures(f"recover:{email}")) >= get_settings().login_max_failures:
        # Still generic: a 429 here would itself leak "this email has been tried before".
        return _GENERIC_RECOVERY_RESPONSE
    _failed_logins.setdefault(f"recover:{email}", []).append(time.monotonic())
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.active:
        raw = secrets.token_urlsafe(32)
        user.setup_token_hash = hash_setup_token(raw)
        user.setup_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_LINK_HOURS)
        db.add(AuditLog(actor_user_id=user.id, action="user.password_reset_requested",
                        entity_type="user", entity_id=user.id))
        db.commit()
        _deliver_reset_link(user, raw)
    return _GENERIC_RECOVERY_RESPONSE


class SetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# A resized JPEG/WebP face photo comfortably fits under this as a base64 data
# URL; it's a backstop against someone posting a multi-MB original, not the
# primary size control (the frontend resizes before upload).
MAX_AVATAR_DATA_URL_LENGTH = 400_000


class ProfileUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    avatar_data_url: str | None = Field(default=None, max_length=MAX_AVATAR_DATA_URL_LENGTH)


@router.post("/set-password", response_model=TokenOut, tags=["app-auth"])
def set_password(payload: SetPasswordIn, db: Db, request: Request):
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
    return _token_response(user, db, request)


@router.post("/change-password", response_model=TokenOut, tags=["app-auth"])
def change_password(payload: ChangePasswordIn, user: CurrentUser, db: Db, request: Request):
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
    return _token_response(user, db, request)


@router.patch("/profile", response_model=UserView, tags=["app-auth"])
def update_profile(payload: ProfileUpdateIn, user: CurrentUser, db: Db):
    """Update your own display name, phone and profile photo.

    No separate "upload image" endpoint -- the photo travels as a data: URL
    in the same PATCH, since it's already resized and tiny by the time the
    frontend sends it. See ProfileUpdateIn.avatar_data_url for the size cap.
    """
    if payload.avatar_data_url is not None and payload.avatar_data_url != "" and not payload.avatar_data_url.startswith("data:image/"):
        raise HTTPException(status_code=422, detail="ছবিটি সঠিক ফরম্যাটে পাঠানো হয়নি।")
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.phone is not None:
        user.phone = payload.phone.strip() or None
    if payload.avatar_data_url is not None:
        user.avatar_data_url = payload.avatar_data_url or None
    db.add(AuditLog(actor_user_id=user.id, action="user.profile_updated",
                    entity_type="user", entity_id=user.id))
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout", tags=["app-auth"])
def logout(user: CurrentUser, db: Db):
    """Revoke every outstanding access and refresh token for this user, every device."""
    user.token_version = int(user.token_version or 0) + 1
    db.add(user)
    now = datetime.now(timezone.utc)
    for session in db.scalars(
        select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
    ):
        session.revoked_at = now
        session.revoked_reason = "logout_all"
    db.add(AuditLog(actor_user_id=user.id, action="user.logged_out",
                    entity_type="user", entity_id=user.id))
    db.commit()
    return {"status": "logged_out"}


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_label: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime


@router.get("/sessions", response_model=list[SessionOut], tags=["app-auth"])
def list_sessions(user: CurrentUser, db: Db):
    """Active (not revoked, not expired) sessions -- AUTH-006 self-service device list."""
    now = datetime.now(timezone.utc)
    sessions = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_used_at.desc())
    ).all()
    return [s for s in sessions if s.expires_at.replace(tzinfo=timezone.utc) >= now]


@router.post("/sessions/{session_id}/revoke", tags=["app-auth"])
def revoke_session(session_id: str, user: CurrentUser, db: Db):
    """Sign out one specific device without touching the caller's own session."""
    session = db.get(UserSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = "user_revoked"
        db.add(AuditLog(actor_user_id=user.id, action="user.session_revoked",
                        entity_type="user_session", entity_id=session.id))
        db.commit()
    return {"status": "revoked"}


class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str


@router.post("/mfa/setup", response_model=MfaSetupOut, tags=["app-auth"])
def setup_mfa(user: CurrentUser, db: Db):
    """Start enrolling MFA: generates a secret, not yet active until /mfa/enable confirms it."""
    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled")
    secret = new_totp_secret()
    user.mfa_totp_secret = secret
    db.commit()
    return MfaSetupOut(
        secret=secret,
        otpauth_uri=provisioning_uri(secret, user.email, get_settings().app_name),
    )


class MfaEnableIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MfaEnableOut(BaseModel):
    recovery_codes: list[str]


@router.post("/mfa/enable", response_model=MfaEnableOut, tags=["app-auth"])
def enable_mfa(payload: MfaEnableIn, user: CurrentUser, db: Db):
    """Confirm enrollment with one real code from the authenticator app, then turn MFA on."""
    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled")
    if not user.mfa_totp_secret:
        raise HTTPException(status_code=400, detail="Call /mfa/setup first")
    if not verify_totp(user.mfa_totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="Incorrect code")
    raw_codes = new_recovery_codes()
    user.mfa_enabled = True
    user.mfa_recovery_codes_json = json.dumps([hash_setup_token(c) for c in raw_codes])
    db.add(AuditLog(actor_user_id=user.id, action="user.mfa_enabled",
                    entity_type="user", entity_id=user.id))
    db.commit()
    return MfaEnableOut(recovery_codes=raw_codes)


class MfaDisableIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@router.post("/mfa/disable", tags=["app-auth"])
def disable_mfa(payload: MfaDisableIn, user: CurrentUser, db: Db):
    """Turn MFA off. Requires the current password, not just a live session."""
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.mfa_enabled = False
    user.mfa_totp_secret = None
    user.mfa_recovery_codes_json = None
    db.add(AuditLog(actor_user_id=user.id, action="user.mfa_disabled",
                    entity_type="user", entity_id=user.id))
    db.commit()
    return {"status": "disabled"}


@router.get("/permissions", tags=["app-auth"])
def my_permissions(membership: CurrentMembership):
    """The caller's role and permissions in the organization named by X-Organization-ID."""
    return {
        "organization_id": membership.organization_id,
        "role": membership.role,
        "permissions": sorted(permissions_for(membership.role)),
    }
