from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.category import Category
from app.models.recurring import RecurringRule
from app.schemas.recurring import (
    RecurringRuleCreate,
    RecurringRuleUpdate,
    RecurringRuleResponse,
)
from app.auth.dependencies import get_current_user, get_user_record
from app.errors import AppException

router = APIRouter(prefix="/recurring", tags=["Recurring Transactions"])


def _to_rule_response(r: RecurringRule, cat_name: str | None = None) -> RecurringRuleResponse:
    return RecurringRuleResponse(
        id=r.id,
        user_id=r.user_id,
        type=r.type,
        amount=r.amount,
        category_id=r.category_id,
        category_name=cat_name,
        payment_method=r.payment_method,
        note=r.note,
        frequency=r.frequency,
        day_of_month=r.day_of_month,
        start_date=r.start_date,
        end_date=r.end_date,
        is_paused=r.is_paused,
        created_at=r.created_at,
    )


@router.post("", response_model=RecurringRuleResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_rule(
    payload: RecurringRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a recurring income or expense rule (FR-048). Monthly frequency only in v1."""
    category = get_user_record(
        db, Category, current_user.id, payload.category_id, "CATEGORY_NOT_FOUND", "Category not found."
    )
    if category.type != payload.type:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CATEGORY_TYPE_MISMATCH",
            message=f"Category '{category.name}' type '{category.type}' does not match rule type '{payload.type}'.",
        )

    if payload.end_date and payload.end_date < payload.start_date:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_DATE_RANGE",
            message="Rule end date cannot be earlier than start date.",
        )

    rule = RecurringRule(
        user_id=current_user.id,
        type=payload.type,
        amount=payload.amount,
        category_id=category.id,
        payment_method=payload.payment_method,
        note=payload.note.strip() if payload.note else None,
        frequency="monthly",
        day_of_month=payload.day_of_month,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_paused=False,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return _to_rule_response(rule, category.name)


@router.get("", response_model=List[RecurringRuleResponse])
def list_recurring_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all recurring rules for the current user (FR-048)."""
    stmt = (
        select(RecurringRule, Category.name.label("category_name"))
        .join(Category, Category.id == RecurringRule.category_id)
        .where(RecurringRule.user_id == current_user.id)
        .order_by(desc(RecurringRule.created_at))
    )
    results = db.execute(stmt).all()
    return [_to_rule_response(r, cat_name) for r, cat_name in results]


@router.get("/{rule_id}", response_model=RecurringRuleResponse)
def get_recurring_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single recurring rule details."""
    rule = get_user_record(
        db, RecurringRule, current_user.id, rule_id, "RULE_NOT_FOUND", "Recurring rule not found."
    )
    cat = db.scalar(select(Category).where(Category.id == rule.category_id))
    return _to_rule_response(rule, cat.name if cat else None)


@router.patch("/{rule_id}", response_model=RecurringRuleResponse)
def update_recurring_rule(
    rule_id: int,
    payload: RecurringRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edit recurring rule (FR-050). Edits apply to future occurrences only."""
    rule = get_user_record(
        db, RecurringRule, current_user.id, rule_id, "RULE_NOT_FOUND", "Recurring rule not found."
    )

    if payload.category_id is not None:
        cat = get_user_record(
            db, Category, current_user.id, payload.category_id, "CATEGORY_NOT_FOUND", "Category not found."
        )
        if cat.type != rule.type:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CATEGORY_TYPE_MISMATCH",
                message=f"Category '{cat.name}' type '{cat.type}' does not match rule type '{rule.type}'.",
            )
        rule.category_id = cat.id

    if payload.amount is not None:
        rule.amount = payload.amount
    if payload.payment_method is not None:
        rule.payment_method = payload.payment_method
    if payload.note is not None:
        rule.note = payload.note.strip() if payload.note else None
    if payload.day_of_month is not None:
        rule.day_of_month = payload.day_of_month
    if payload.end_date is not None:
        rule.end_date = payload.end_date

    db.commit()
    db.refresh(rule)

    cat = db.scalar(select(Category).where(Category.id == rule.category_id))
    return _to_rule_response(rule, cat.name if cat else None)


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
def delete_recurring_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete recurring rule (FR-050)."""
    rule = get_user_record(
        db, RecurringRule, current_user.id, rule_id, "RULE_NOT_FOUND", "Recurring rule not found."
    )
    db.delete(rule)
    db.commit()
    return {"message": "Recurring rule deleted successfully."}


@router.post("/{rule_id}/pause", response_model=RecurringRuleResponse)
def pause_recurring_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pause recurring rule (FR-050)."""
    rule = get_user_record(
        db, RecurringRule, current_user.id, rule_id, "RULE_NOT_FOUND", "Recurring rule not found."
    )
    rule.is_paused = True
    db.commit()
    db.refresh(rule)
    cat = db.scalar(select(Category).where(Category.id == rule.category_id))
    return _to_rule_response(rule, cat.name if cat else None)


@router.post("/{rule_id}/resume", response_model=RecurringRuleResponse)
def resume_recurring_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resume recurring rule (FR-050)."""
    rule = get_user_record(
        db, RecurringRule, current_user.id, rule_id, "RULE_NOT_FOUND", "Recurring rule not found."
    )
    rule.is_paused = False
    db.commit()
    db.refresh(rule)
    cat = db.scalar(select(Category).where(Category.id == rule.category_id))
    return _to_rule_response(rule, cat.name if cat else None)
