from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.goal import Goal, GoalEntry
from app.models.notification import Notification
from app.schemas.goal import (
    GoalCreate,
    GoalUpdate,
    GoalFundAction,
    GoalResponse,
    GoalDetailResponse,
    GoalEntryResponse,
)
from app.auth.dependencies import get_current_user, get_user_record
from app.errors import AppException

router = APIRouter(prefix="/goals", tags=["Savings Goals"])


def _to_goal_response(g: Goal) -> GoalResponse:
    pct = round((g.saved_amount / g.target_amount) * 100, 1) if g.target_amount > 0 else 0.0
    return GoalResponse(
        id=g.id,
        user_id=g.user_id,
        name=g.name,
        target_amount=g.target_amount,
        saved_amount=g.saved_amount,
        deadline=g.deadline,
        status=g.status,
        created_at=g.created_at,
        percentage=min(pct, 100.0),
    )


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a savings goal (FR-053)."""
    goal = Goal(
        user_id=current_user.id,
        name=payload.name.strip(),
        target_amount=payload.target_amount,
        saved_amount=0,
        deadline=payload.deadline,
        status="in_progress",
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _to_goal_response(goal)


@router.get("", response_model=List[GoalResponse])
def list_goals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all savings goals for the user (FR-053)."""
    goals = db.scalars(
        select(Goal).where(Goal.user_id == current_user.id).order_by(Goal.created_at.desc())
    ).all()
    return [_to_goal_response(g) for g in goals]


@router.get("/{goal_id}", response_model=GoalDetailResponse)
def get_goal_detail(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get goal details and complete entry history (FR-053, FR-054)."""
    goal = get_user_record(db, Goal, current_user.id, goal_id, "GOAL_NOT_FOUND", "Goal not found.")
    entries = db.scalars(
        select(GoalEntry).where(GoalEntry.goal_id == goal.id).order_by(desc(GoalEntry.created_at))
    ).all()

    base = _to_goal_response(goal)
    return GoalDetailResponse(
        **base.model_dump(),
        entries=[
            GoalEntryResponse(
                id=e.id,
                goal_id=e.goal_id,
                amount=e.amount,
                created_at=e.created_at,
            )
            for e in entries
        ],
    )


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edit goal properties (FR-053)."""
    goal = get_user_record(db, Goal, current_user.id, goal_id, "GOAL_NOT_FOUND", "Goal not found.")

    if payload.name is not None:
        goal.name = payload.name.strip()
    if payload.target_amount is not None:
        goal.target_amount = payload.target_amount
        if goal.saved_amount >= goal.target_amount:
            goal.status = "completed"
        else:
            goal.status = "in_progress"
    if payload.deadline is not None:
        goal.deadline = payload.deadline

    db.commit()
    db.refresh(goal)
    return _to_goal_response(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_200_OK)
def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a savings goal (FR-053, FR-055).
    Deleting a goal automatically returns all saved funds to the wallet with row locking.
    """
    goal = get_user_record(db, Goal, current_user.id, goal_id, "GOAL_NOT_FOUND", "Goal not found.")

    # Return funds to wallet if saved_amount > 0
    if goal.saved_amount > 0:
        wallet = db.scalar(
            select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
        )
        if wallet:
            wallet.current_balance += goal.saved_amount

    db.delete(goal)
    db.commit()
    return {"message": "Goal deleted and saved funds returned to wallet."}


@router.post("/{goal_id}/contribute", response_model=GoalResponse)
def contribute_to_goal(
    goal_id: int,
    payload: GoalFundAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Contribute funds to a savings goal (FR-054, FR-055).
    Moves funds from wallet to goal with row locking. Triggers completion notification when target reached.
    """
    goal = get_user_record(db, Goal, current_user.id, goal_id, "GOAL_NOT_FOUND", "Goal not found.")

    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )
    if not wallet:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WALLET_NOT_INITIALIZED",
            message="Wallet not initialized.",
        )

    if wallet.current_balance < payload.amount:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INSUFFICIENT_FUNDS",
            message=f"Contribution of ₹{payload.amount} exceeds wallet balance of ₹{wallet.current_balance}.",
        )

    wallet.current_balance -= payload.amount
    goal.saved_amount += payload.amount

    # Record entry history
    entry = GoalEntry(goal_id=goal.id, amount=payload.amount)
    db.add(entry)

    # Check goal completion (FR-055)
    if goal.saved_amount >= goal.target_amount and goal.status != "completed":
        goal.status = "completed"
        notif = Notification(
            user_id=current_user.id,
            type="goal_completed",
            payload={
                "message": f"Congratulations! You reached your savings goal target for '{goal.name}' (₹{goal.saved_amount}/₹{goal.target_amount}).",
                "goal_id": goal.id,
            },
            is_read=False,
        )
        db.add(notif)

    db.commit()
    db.refresh(goal)
    return _to_goal_response(goal)


@router.post("/{goal_id}/withdraw", response_model=GoalResponse)
def withdraw_from_goal(
    goal_id: int,
    payload: GoalFundAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Withdraw funds from a savings goal back to the wallet (FR-054).
    Moves funds from goal to wallet with row locking.
    """
    goal = get_user_record(db, Goal, current_user.id, goal_id, "GOAL_NOT_FOUND", "Goal not found.")

    if goal.saved_amount < payload.amount:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INSUFFICIENT_GOAL_FUNDS",
            message=f"Withdrawal amount of ₹{payload.amount} exceeds saved amount of ₹{goal.saved_amount}.",
        )

    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )
    if not wallet:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WALLET_NOT_INITIALIZED",
            message="Wallet not initialized.",
        )

    goal.saved_amount -= payload.amount
    wallet.current_balance += payload.amount

    if goal.saved_amount < goal.target_amount:
        goal.status = "in_progress"

    # Record negative entry in history
    entry = GoalEntry(goal_id=goal.id, amount=-payload.amount)
    db.add(entry)

    db.commit()
    db.refresh(goal)
    return _to_goal_response(goal)
