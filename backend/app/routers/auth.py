from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select, or_, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.limiter import limiter
from app.models.user import User
from app.models.session import UserSession
from app.models.wallet import Wallet
from app.auth.security import (
    hash_password,
    verify_password,
    hash_refresh_token,
    generate_refresh_token,
    create_access_token,
)
from app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
    SessionResponse,
)
from app.auth.dependencies import get_current_user
from app.services.recurring_service import apply_recurring_for_user
from app.errors import AppException

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, refresh_token: str):
    """Set secure httpOnly refresh token cookie."""
    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=settings.JWT_REFRESH_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response):
    """Clear refresh token cookie."""
    is_prod = settings.ENVIRONMENT == "production"
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        path="/api/v1/auth",
    )


def _extract_ip_and_ua(request: Request):
    ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    ua = request.headers.get("user-agent")
    return ip, ua[:500] if ua else None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user account with email, username, and password (FR-001 - FR-003, FR-012)."""
    # Check duplicate email
    existing_email = db.scalar(select(User).where(User.email == payload.email))
    if existing_email:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_EMAIL",
            message="An account with this email address already exists.",
        )

    # Check duplicate username
    existing_username = db.scalar(select(User).where(User.username == payload.username))
    if existing_username:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_USERNAME",
            message="This username is already taken. Please choose another.",
        )

    # Hash password with Argon2
    password_hash = hash_password(payload.password)

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=password_hash,
        auth_provider="local",
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create initial session
    now = datetime.now(timezone.utc)
    raw_refresh = generate_refresh_token()
    token_hash = hash_refresh_token(raw_refresh)
    ip, ua = _extract_ip_and_ua(request)

    session_row = UserSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        user_agent=ua,
        ip=ip,
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=settings.JWT_REFRESH_DAYS),
    )
    db.add(session_row)
    db.commit()

    _set_refresh_cookie(response, raw_refresh)
    access_token = create_access_token(user.id, user.username)

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        has_wallet=False,
        created_at=user.created_at,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_MINUTES * 60,
        user=user_resp,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate with email or username and password (FR-004 - FR-005, NFR-007)."""
    login_id = payload.login.strip().lower()
    user = db.scalar(
        select(User).where(or_(User.email == login_id, User.username == login_id))
    )

    # Generic error message to prevent account enumeration (NFR-007)
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid login credentials provided.",
        )

    now = datetime.now(timezone.utc)
    raw_refresh = generate_refresh_token()
    token_hash = hash_refresh_token(raw_refresh)
    ip, ua = _extract_ip_and_ua(request)

    session_row = UserSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        user_agent=ua,
        ip=ip,
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=settings.JWT_REFRESH_DAYS),
    )
    db.add(session_row)
    db.commit()

    _set_refresh_cookie(response, raw_refresh)
    access_token = create_access_token(user.id, user.username)

    # Catch up missed recurring transactions on login (FR-052b)
    try:
        apply_recurring_for_user(db, user.id)
    except Exception:
        # Prevent catch-up failures from blocking user login
        db.rollback()

    # Check if user has initialized their wallet (FR-009)
    has_wallet = db.scalar(select(Wallet.id).where(Wallet.user_id == user.id)) is not None

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        has_wallet=has_wallet,
        created_at=user.created_at,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_MINUTES * 60,
        user=user_resp,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token_endpoint(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    """Exchange rotating refresh token for a new access token (FR-006)."""
    raw_token = None
    if payload and payload.refresh_token:
        raw_token = payload.refresh_token
    elif "refresh_token" in request.cookies:
        raw_token = request.cookies.get("refresh_token")

    if not raw_token:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="REFRESH_TOKEN_REQUIRED",
            message="Valid refresh token required.",
        )

    token_hash = hash_refresh_token(raw_token)
    session_row = db.scalar(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash)
    )

    now = datetime.now(timezone.utc)
    if not session_row:
        _clear_refresh_cookie(response)
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token invalid.",
        )

    # If session is already revoked, potential token reuse attempt: revoke all for user
    if session_row.revoked_at is not None:
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == session_row.user_id)
            .values(revoked_at=now)
        )
        db.commit()
        _clear_refresh_cookie(response)
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="SESSION_REVOKED",
            message="Session has been revoked due to token reuse detection.",
        )

    # Check token expiration
    if session_row.expires_at <= now:
        session_row.revoked_at = now
        db.commit()
        _clear_refresh_cookie(response)
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="REFRESH_TOKEN_EXPIRED",
            message="Refresh token has expired. Please log in again.",
        )

    # Rotate refresh token
    new_raw_refresh = generate_refresh_token()
    new_token_hash = hash_refresh_token(new_raw_refresh)

    session_row.refresh_token_hash = new_token_hash
    session_row.last_used_at = now
    session_row.expires_at = now + timedelta(days=settings.JWT_REFRESH_DAYS)
    db.commit()

    user = db.scalar(select(User).where(User.id == session_row.user_id))
    if not user:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_NOT_FOUND",
            message="Associated user not found.",
        )

    _set_refresh_cookie(response, new_raw_refresh)
    access_token = create_access_token(user.id, user.username)
    has_wallet = db.scalar(select(Wallet.id).where(Wallet.user_id == user.id)) is not None

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        has_wallet=has_wallet,
        created_at=user.created_at,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_MINUTES * 60,
        user=user_resp,
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    """Revoke the current session and clear cookie (FR-007)."""
    raw_token = None
    if payload and payload.refresh_token:
        raw_token = payload.refresh_token
    elif "refresh_token" in request.cookies:
        raw_token = request.cookies.get("refresh_token")

    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        session_row = db.scalar(
            select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        )
        if session_row:
            session_row.revoked_at = datetime.now(timezone.utc)
            db.commit()

    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully."}


@router.post("/logout-all")
def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke all sessions across all devices for the current user (FR-007)."""
    now = datetime.now(timezone.utc)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
    _clear_refresh_cookie(response)
    return {"message": "Logged out of all devices successfully."}


@router.get("/sessions", response_model=List[SessionResponse])
def get_user_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all non-revoked sessions for the current user (FR-005)."""
    raw_token = request.cookies.get("refresh_token")
    current_hash = hash_refresh_token(raw_token) if raw_token else None

    sessions = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_used_at.desc())
    ).all()

    return [
        SessionResponse(
            id=s.id,
            user_agent=s.user_agent,
            ip=s.ip,
            created_at=s.created_at,
            last_used_at=s.last_used_at,
            expires_at=s.expires_at,
            is_current=(current_hash is not None and s.refresh_token_hash == current_hash),
        )
        for s in sessions
    ]
