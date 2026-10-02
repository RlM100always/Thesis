"""Local prototype identity, optional JWTs, and tenant authorization.

Google sign-in is outside the current thesis implementation scope. During local
development an absent bearer token resolves to one stable prototype owner.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .domain_models import Membership, Organization, User

bearer = HTTPBearer(auto_error=False)


def _issue_token(
    user_id: str, token_type: str, lifetime: timedelta, token_version: int,
    sid: str | None = None, jti: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "typ": token_type,
        "tv": token_version,
        "iss": settings.app_name,
        "aud": settings.app_name,
        "iat": now,
        "exp": now + lifetime,
    }
    if sid is not None:
        payload["sid"] = sid
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, token_version: int = 0, sid: str | None = None) -> str:
    return _issue_token(
        user_id, "access", timedelta(minutes=get_settings().access_token_minutes), token_version, sid=sid,
    )


def create_refresh_token(user_id: str, token_version: int = 0, sid: str | None = None, jti: str | None = None) -> str:
    return _issue_token(
        user_id, "refresh", timedelta(days=get_settings().refresh_token_days), token_version, sid=sid, jti=jti,
    )


def create_mfa_challenge_token(user_id: str, token_version: int = 0) -> str:
    """Short-lived ticket proving "password already verified, MFA code still owed".

    Never accepted by ``get_current_user`` (wrong ``typ``) and never usable to
    mint a refresh token either -- it is good for exactly one call to
    ``/auth/mfa/verify`` within 5 minutes.
    """
    return _issue_token(user_id, "mfa", timedelta(minutes=5), token_version)


def decode_token_claims(token: str, expected_type: str = "access") -> dict:
    """Verify signature, issuer, audience, expiry and token type; return the claims.

    A refresh token must never authenticate an API call and an access token must
    never mint new tokens, so the type is checked, not assumed.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
            audience=settings.app_name,
        )
        if not payload.get("sub"):
            raise jwt.InvalidTokenError("missing subject")
        # Tokens issued before the ``typ`` claim existed are access tokens.
        if payload.get("typ", "access") != expected_type:
            raise jwt.InvalidTokenError("wrong token type")
        return payload
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def decode_access_token(token: str) -> str:
    return str(decode_token_claims(token, "access")["sub"])


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        settings = get_settings()
        if settings.auth_mode == "development" and not settings.is_production:
            user = db.scalar(select(User).where(User.email == "developer@bsmart.local"))
            if user is None:
                user = User(email="developer@bsmart.local", display_name="Development Owner", is_platform_admin=True)
                db.add(user)
                db.commit()
                db.refresh(user)
            elif not user.is_platform_admin:
                user.is_platform_admin = True
                db.commit()
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_token_claims(credentials.credentials, "access")
    user = db.get(User, str(claims["sub"]))
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Unknown or inactive user")
    if int(claims.get("tv", 0)) != int(user.token_version or 0):
        # Logged out or password changed since this token was issued.
        raise HTTPException(
            status_code=401, detail="Session expired, please sign in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_org_membership(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
) -> Membership:
    if not organization_id:
        raise HTTPException(status_code=400, detail="X-Organization-ID header is required")
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == current_user.id,
            Membership.active.is_(True),
        )
    )
    if membership is None:
        # Do not reveal whether another tenant exists.
        raise HTTPException(status_code=404, detail="Organization not found")
    org = db.get(Organization, organization_id)
    if org is not None and org.suspended_at is not None:
        raise HTTPException(
            status_code=403,
            detail=org.suspended_reason or "This business has been suspended. Contact support.",
        )
    return membership


def get_platform_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Gate for `/api/platform/*` — every organization, not just one tenant.

    Deliberately not part of the per-org permission matrix in
    `api/permissions.py`: that matrix answers "what can this person do inside
    the organization named by X-Organization-ID", a question platform routes
    don't ask at all.
    """
    if not current_user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin access required")
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentMembership = Annotated[Membership, Depends(get_org_membership)]
