"""Shared FastAPI dependencies: authentication and rate limiting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import UploadEvent, User
from app.security import decode_access_token

# auto_error=False so guest access stays possible on endpoints that allow it.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve the bearer token to a user, or ``None`` for guests."""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    """Require an authenticated, active user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def client_ip(request: Request) -> str:
    """Best-effort client IP, honouring a reverse proxy's X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_upload_rate_limit(db: Session, user: User | None, ip: str) -> None:
    """Cap uploads per hour so inference resources cannot be trivially drained.

    Registered users are counted by account; guests by IP address.
    """
    window_start = datetime.now(UTC) - timedelta(hours=1)
    limit = settings.upload_rate_limit_per_hour if user else settings.guest_rate_limit_per_hour

    condition = (UploadEvent.user_id == user.id) if user else (UploadEvent.client_ip == ip)
    recent = (
        db.scalar(
            select(func.count())
            .select_from(UploadEvent)
            .where(UploadEvent.created_at >= window_start, condition)
        )
        or 0
    )

    if recent >= limit:
        scope = "account" if user else "guest (unauthenticated)"
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Upload limit reached for this {scope}: {limit} uploads per hour. "
                + ("Sign in for a higher limit." if not user else "Try again later.")
            ),
            headers={"Retry-After": "3600"},
        )

    # Commit the attempt now, not with the job. A rejected upload still consumed
    # bandwidth, disk and validation work; if the event only landed alongside a
    # successfully created job, an attacker could send unlimited malformed files
    # and never be counted.
    db.add(UploadEvent(user_id=user.id if user else None, client_ip=ip))
    db.commit()
