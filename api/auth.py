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
from .domain_models import Membership, User

bearer = HTTPBearer(auto_error=False)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iss": settings.app_name,
        "aud": settings.app_name,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
            audience=settings.app_name,
        )
        subject = payload.get("sub")
        if not subject:
            raise jwt.InvalidTokenError("missing subject")
        return str(subject)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        settings = get_settings()
        if settings.auth_mode == "development" and not settings.is_production:
            user = db.scalar(select(User).where(User.email == "developer@bsmart.local"))
            if user is None:
                user = User(email="developer@bsmart.local", display_name="Development Owner")
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, decode_access_token(credentials.credentials))
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Unknown or inactive user")
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
    return membership


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentMembership = Annotated[Membership, Depends(get_org_membership)]
