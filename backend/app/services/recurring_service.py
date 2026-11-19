from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy import select, delete, and_
from sqlalchemy.orm import Session

from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.recurring import RecurringRule, RecurringRun
from app.models.split import Split, SplitParticipant
from app.models.notification import Notification
from app.services.time_utils import (
    get_current_ist_date,
    clamp_day_to_month,
    ensure_utc,
    utc_now,
)
from app.services.budget_service import check_and_trigger_budget_alerts


def apply_recurring_for_user(db: Session, user_id: int, up_to_date: date | None = None) -> Dict[str, int]:
    """
    Catch up / apply recurring transaction occurrences for a user up to target date (FR-051, FR-052a, FR-052b).
    Enforces idempotency using recurring_runs table.
    Row locks wallet. If expense exceeds balance, skips occurrence and sends notification.
    """
    target_d = up_to_date or get_current_ist_date()

    rules = db.scalars(
        select(RecurringRule).where(
            RecurringRule.user_id == user_id,
            RecurringRule.is_paused.is_(False),
            RecurringRule.start_date <= target_d,
        )
    ).all()

    applied_count = 0
    skipped_count = 0

    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == user_id).with_for_update()
    )
    if not wallet:
        return {"applied": 0, "skipped": 0}

    for rule in rules:
        # Determine all months from start_date to target_d
        cur_year = rule.start_date.year
        cur_month = rule.start_date.month

        end_year = target_d.year
        end_month = target_d.month

        while (cur_year < end_year) or (cur_year == end_year and cur_month <= end_month):
            clamped_day = clamp_day_to_month(cur_year, cur_month, rule.day_of_month)
            occurrence_date = date(cur_year, cur_month, clamped_day)

            # Check validity against start_date, target_d, and rule.end_date
            if rule.start_date <= occurrence_date <= target_d:
                if rule.end_date is None or occurrence_date <= rule.end_date:
                    # Check idempotency: has this rule already run on this date?
                    already_run = db.scalar(
                        select(RecurringRun.id).where(
                            RecurringRun.rule_id == rule.id,
                            RecurringRun.run_date == occurrence_date,
                        )
                    )
                    if not already_run:
                        if rule.type == "income":
                            wallet.current_balance += rule.amount
                            tx = Transaction(
                                user_id=user_id,
                                wallet_id=wallet.id,
                                type="income",
                                amount=rule.amount,
                                date=occurrence_date,
                                category_id=rule.category_id,
                                payment_method=rule.payment_method,
                                note=rule.note or "Recurring Income",
                                source="recurring",
                                read_only=False,
                            )
                            db.add(tx)
                            run = RecurringRun(
                                rule_id=rule.id,
                                run_date=occurrence_date,
                                status="applied",
                            )
                            db.add(run)
                            notif = Notification(
                                user_id=user_id,
                                type="recurring_added",
                                payload={
                                    "message": f"Recurring income of ₹{rule.amount} applied ({rule.note or 'Income'}).",
                                    "rule_id": rule.id,
                                    "date": str(occurrence_date),
                                },
                                is_read=False,
                            )
                            db.add(notif)
                            applied_count += 1

                        else:  # expense
                            if wallet.current_balance >= rule.amount:
                                wallet.current_balance -= rule.amount
                                tx = Transaction(
                                    user_id=user_id,
                                    wallet_id=wallet.id,
                                    type="expense",
                                    amount=rule.amount,
                                    date=occurrence_date,
                                    category_id=rule.category_id,
                                    payment_method=rule.payment_method,
                                    note=rule.note or "Recurring Expense",
                                    source="recurring",
                                    read_only=False,
                                )
                                db.add(tx)
                                run = RecurringRun(
                                    rule_id=rule.id,
                                    run_date=occurrence_date,
                                    status="applied",
                                )
                                db.add(run)
                                notif = Notification(
                                    user_id=user_id,
                                    type="recurring_added",
                                    payload={
                                        "message": f"Recurring expense of ₹{rule.amount} applied ({rule.note or 'Expense'}).",
                                        "rule_id": rule.id,
                                        "date": str(occurrence_date),
                                    },
                                    is_read=False,
                                )
                                db.add(notif)
                                check_and_trigger_budget_alerts(db, user_id, occurrence_date)
                                applied_count += 1
                            else:
                                # Insufficient balance: skip and notify (FR-051)
                                run = RecurringRun(
                                    rule_id=rule.id,
                                    run_date=occurrence_date,
                                    status="skipped",
                                )
                                db.add(run)
                                notif = Notification(
                                    user_id=user_id,
                                    type="recurring_skipped",
                                    payload={
                                        "message": f"{rule.note or 'Recurring expense'} of ₹{rule.amount} not added: insufficient balance.",
                                        "rule_id": rule.id,
                                        "date": str(occurrence_date),
                                    },
                                    is_read=False,
                                )
                                db.add(notif)
                                skipped_count += 1

            # Advance to next month
            if cur_month == 12:
                cur_year += 1
                cur_month = 1
            else:
                cur_month += 1

    db.commit()
    return {"applied": applied_count, "skipped": skipped_count}


def expire_pending_splits(db: Session, as_of: datetime | None = None) -> int:
    """
    Expire split requests that have passed their 7-day expiration (FR-066, FR-067).
    """
    now = ensure_utc(as_of or utc_now())
    all_pending_parts = db.scalars(
        select(SplitParticipant)
        .join(Split, Split.id == SplitParticipant.split_id)
        .where(
            SplitParticipant.status == "pending",
        )
    ).all()

    count = 0
    for p in all_pending_parts:
        if ensure_utc(p.split.expires_at) <= now:
            p.status = "expired"
        p.responded_at = now
        split_obj = p.split
        notif = Notification(
            user_id=split_obj.payer_id,
            type="split_expired",
            payload={
                "message": f"Split request for ₹{p.share_amount} in '{split_obj.note or 'Split'}' expired after 7 days.",
                "split_id": split_obj.id,
            },
            is_read=False,
        )
        db.add(notif)
        count += 1

    db.commit()
    return count


def prune_old_notifications(db: Session, older_than_days: int = 90) -> int:
    """
    Prune notifications older than 90 days (FR-081).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    result = db.execute(
        delete(Notification).where(Notification.created_at <= cutoff)
    )
    db.commit()
    return result.rowcount or 0


def run_daily_job(db: Session) -> Dict[str, Any]:
    """Execute complete daily job tasks (FR-052b, FR-067, FR-081)."""
    # 1. Apply recurring for all active wallets
    user_ids = list(db.scalars(select(Wallet.user_id)).all())
    total_applied = 0
    total_skipped = 0
    today = get_current_ist_date()

    for uid in user_ids:
        res = apply_recurring_for_user(db, uid, today)
        total_applied += res["applied"]
        total_skipped += res["skipped"]

    # 2. Expire pending splits
    expired_splits = expire_pending_splits(db)

    # 3. Prune old notifications
    pruned_notifs = prune_old_notifications(db, 90)

    return {
        "status": "success",
        "date": str(today),
        "recurring_applied": total_applied,
        "recurring_skipped": total_skipped,
        "splits_expired": expired_splits,
        "notifications_pruned": pruned_notifs,
    }
