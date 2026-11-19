from typing import Type, TypeVar, Any
from fastapi import Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.session import UserSession
from app.auth.security import decode_access_token
from app.errors import AppException

security_bearer = HTTPBearer(auto_error=False)

T = TypeVar("T")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Centralized authentication dependency validating JWT access token."""
    token: str | None = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Authentication credentials required",
        )

    payload = decode_access_token(token)
    if not payload:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message="Invalid or expired access token",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message="Token subject missing",
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message="Invalid user identifier in token",
        )

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_NOT_FOUND",
            message="User account no longer exists",
        )

    # Store user and user_id in request state for convenient downstream access
    request.state.current_user = user
    request.state.current_user_id = user.id
    return user


def get_user_record(
    db: Session,
    model: Type[T],
    user_id: int,
    record_id: int,
    error_code: str = "NOT_FOUND",
    error_message: str = "Record not found",
) -> T:
    """
    Centralized data-isolation helper (NFR-002).
    Ensures that access to user-owned resources is strictly scoped to the authenticated user.
    """
    stmt = select(model).where(model.id == record_id, model.user_id == user_id)
    record = db.scalar(stmt)
    if not record:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=error_code,
            message=error_message,
        )
    return record


def user_scoped_query(db: Session, model: Type[T], user_id: int):
    """
    Centralized query builder helper (NFR-002) pre-filtering by user_id.
    """
    return select(model).where(model.user_id == user_id)
