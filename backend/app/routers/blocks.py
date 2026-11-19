from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.block import Block
from app.schemas.block import BlockCreate, BlockResponse
from app.auth.dependencies import get_current_user
from app.errors import AppException

router = APIRouter(prefix="/blocks", tags=["User Blocking"])


@router.get("", response_model=List[BlockResponse])
def list_blocked_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users blocked by the current user (FR-072)."""
    stmt = (
        select(Block, User.username.label("blocked_username"))
        .join(User, User.id == Block.blocked_id)
        .where(Block.blocker_id == current_user.id)
        .order_by(Block.created_at.desc())
    )
    results = db.execute(stmt).all()
    return [
        BlockResponse(
            id=b.id,
            blocked_id=b.blocked_id,
            blocked_username=u_name,
            created_at=b.created_at,
        )
        for b, u_name in results
    ]


@router.post("", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
def block_user(
    payload: BlockCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Block another user by username (FR-072). Blocked users cannot send split requests or invites."""
    target_username = payload.username.strip().lower()

    if target_username == current_user.username:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CANNOT_BLOCK_SELF",
            message="You cannot block yourself.",
        )

    target_user = db.scalar(select(User).where(User.username == target_username))
    if not target_user:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="USER_NOT_FOUND",
            message="User not found.",
        )

    # Check if already blocked
    existing = db.scalar(
        select(Block).where(
            Block.blocker_id == current_user.id,
            Block.blocked_id == target_user.id,
        )
    )
    if existing:
        return BlockResponse(
            id=existing.id,
            blocked_id=existing.blocked_id,
            blocked_username=target_user.username,
            created_at=existing.created_at,
        )

    block = Block(blocker_id=current_user.id, blocked_id=target_user.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    return BlockResponse(
        id=block.id,
        blocked_id=block.blocked_id,
        blocked_username=target_user.username,
        created_at=block.created_at,
    )


@router.delete("/{username}", status_code=status.HTTP_200_OK)
def unblock_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unblock a user by username (FR-072)."""
    target_username = username.strip().lower()
    target_user = db.scalar(select(User).where(User.username == target_username))
    if not target_user:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="USER_NOT_FOUND",
            message="User not found.",
        )

    db.execute(
        delete(Block).where(
            Block.blocker_id == current_user.id,
            Block.blocked_id == target_user.id,
        )
    )
    db.commit()
    return {"message": f"Successfully unblocked {target_username}."}
