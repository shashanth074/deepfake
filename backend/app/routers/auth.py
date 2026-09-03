"""Registration and JWT login."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    """Create an account and return a token so the client is logged in at once."""
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Exchange credentials for a bearer token."""
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user is None:
        # Hash anyway so an unregistered email does not answer faster than a
        # registered one and leak which accounts exist.
        hash_password(payload.password)
        password_ok = False
    else:
        password_ok = verify_password(payload.password, user.hashed_password)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")
    return _issue_token(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's profile."""
    return user


def _issue_token(user: User) -> Token:
    token, expires_in = create_access_token(user.id, {"email": user.email})
    return Token(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )
