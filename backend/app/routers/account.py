from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.split import Split, SplitParticipant
from app.models.group import Group, GroupMember
from app.models.notification import Notification
from app.auth.security import verify_password, create_access_token
from app.auth.schemas import (
    UserResponse,
    ChangeUsernameRequest,
    DeleteAccountRequest,
)
from app.auth.dependencies import get_current_user
from app.errors import AppException

router = APIRouter(prefix="/me", tags=["Account"])


@router.get("", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the current user profile with wallet initialization status."""
    has_wallet = db.scalar(select(Wallet.id).where(Wallet.user_id == current_user.id)) is not None
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        has_wallet=has_wallet,
        created_at=current_user.created_at,
    )


@router.patch("/username", response_model=UserResponse)
def change_username(
    payload: ChangeUsernameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change username (FR-008). Frees old username immediately."""
    new_username = payload.new_username

    if new_username == current_user.username:
        has_wallet = db.scalar(select(Wallet.id).where(Wallet.user_id == current_user.id)) is not None
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            username=current_user.username,
            has_wallet=has_wallet,
            created_at=current_user.created_at,
        )

    # Check uniqueness
    existing = db.scalar(select(User).where(func.lower(User.username) == new_username.lower()))
    if existing:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_USERNAME",
            message="This username is already taken.",
        )

    current_user.username = new_username
    db.commit()
    db.refresh(current_user)

    has_wallet = db.scalar(select(Wallet.id).where(Wallet.user_id == current_user.id)) is not None
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        has_wallet=has_wallet,
        created_at=current_user.created_at,
    )


@router.delete("", status_code=status.HTTP_200_OK)
def delete_account(
    payload: DeleteAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Account deletion (FR-011):
    1. Requires password confirmation.
    2. Pending splits created by or addressed to user are cancelled and parties notified.
    3. Personal data deleted via cascading relationships.
    4. Accepted split history owned by other users is kept; user is set to NULL ("Deleted user").
    5. Group creator succession (FR-077) applied.
    6. Username freed.
    """
    if not current_user.password_hash or not verify_password(payload.password, current_user.password_hash):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_PASSWORD",
            message="Incorrect password confirmation.",
        )

    now = datetime.now(timezone.utc)
    user_id = current_user.id
    username = current_user.username

    # 1. Cancel pending splits created by this user
    created_splits = db.scalars(
        select(Split).where(Split.payer_id == user_id, Split.status != "cancelled")
    ).all()
    for s in created_splits:
        s.status = "cancelled"
        # Notify participants
        for part in s.participants:
            if part.user_id and part.user_id != user_id:
                notif = Notification(
                    user_id=part.user_id,
                    type="split_cancelled",
                    payload={
                        "message": f"Split '{s.note or 'Split'}' was cancelled because the creator deleted their account.",
                        "split_id": s.id,
                    },
                    is_read=False,
                )
                db.add(notif)

    # Cancel pending requests addressed to this user in splits created by others
    addressed_pending_parts = db.scalars(
        select(SplitParticipant)
        .join(Split, Split.id == SplitParticipant.split_id)
        .where(
            SplitParticipant.user_id == user_id,
            SplitParticipant.status == "pending",
            Split.payer_id != user_id,
        )
    ).all()
    for part in addressed_pending_parts:
        part.status = "rejected"
        split_obj = part.split
        notif = Notification(
            user_id=split_obj.payer_id,
            type="split_rejected",
            payload={
                "message": f"{username} deleted their account; their pending share of ₹{part.share_amount} was rejected.",
                "split_id": split_obj.id,
            },
            is_read=False,
        )
        db.add(notif)

    # 2. Preserve accepted split history owned by other users: detach user_id -> NULL
    db.execute(
        update(SplitParticipant)
        .where(SplitParticipant.user_id == user_id)
        .values(user_id=None)
    )

    # 3. Handle Group memberships and creator succession (FR-077, FR-078)
    created_groups = db.scalars(select(Group).where(Group.creator_id == user_id)).all()
    for grp in created_groups:
        # Find earliest-joined active remaining member
        successor = db.scalar(
            select(GroupMember)
            .where(GroupMember.group_id == grp.id, GroupMember.user_id != user_id, GroupMember.status == "active")
            .order_by(GroupMember.joined_at.asc(), GroupMember.id.asc())
        )
        if successor:
            grp.creator_id = successor.user_id
        else:
            grp.creator_id = None

    # Remove group memberships
    db.execute(delete(GroupMember).where(GroupMember.user_id == user_id))

    # Auto-delete groups that now have 0 members
    for grp in created_groups:
        remaining_count = db.scalar(
            select(func.count(GroupMember.id)).where(GroupMember.group_id == grp.id)
        )
        if remaining_count == 0:
            db.delete(grp)

    # 4. Delete the User record itself (cascades wallet, sessions, categories, transactions, budgets, goals, recurring, blocks, notifications)
    db.delete(current_user)
    db.commit()

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="none" if settings.ENVIRONMENT == "production" else "lax",
        path="/api/v1/auth",
    )

    return {"message": "Account successfully deleted."}
