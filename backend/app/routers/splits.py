from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.split import Split, SplitParticipant
from app.models.group import Group, GroupMember
from app.models.notification import Notification
from app.schemas.split import (
    SplitCreate,
    SplitUpdate,
    SplitResponse,
    SplitParticipantResponse,
    ParticipantInput,
)
from app.auth.dependencies import get_current_user
from app.services.split_calculator import calculate_participant_shares
from app.services.block_service import is_user_blocked
from app.services.time_utils import get_current_ist_date, ensure_utc, utc_now
from app.services.budget_service import check_and_trigger_budget_alerts
from app.errors import AppException

router = APIRouter(prefix="/splits", tags=["Bill Splitting"])


def _to_split_response(s: Split, current_user_id: int, db: Session) -> SplitResponse:
    payer = db.scalar(select(User).where(User.id == s.payer_id))
    group = db.scalar(select(Group).where(Group.id == s.group_id)) if s.group_id else None
    bearer = db.scalar(select(User).where(User.id == s.remainder_bearer_id)) if s.remainder_bearer_id else None

    # Participants
    p_stmt = (
        select(SplitParticipant, User.username)
        .outerjoin(User, User.id == SplitParticipant.user_id)
        .where(SplitParticipant.split_id == s.id)
        .order_by(SplitParticipant.id.asc())
    )
    p_results = db.execute(p_stmt).all()

    participants_resp = []
    user_status = None
    user_share = None

    for part, u_name in p_results:
        display_name = u_name if part.user_id is not None else "Deleted user"
        is_payer = (part.user_id == s.payer_id)
        if part.user_id == current_user_id:
            user_status = part.status
            user_share = part.share_amount

        participants_resp.append(
            SplitParticipantResponse(
                id=part.id,
                user_id=part.user_id,
                username=display_name,
                share_amount=part.share_amount,
                status=part.status,
                responded_at=part.responded_at,
                is_payer=is_payer,
            )
        )

    return SplitResponse(
        id=s.id,
        payer_id=s.payer_id,
        payer_username=payer.username if payer else "Deleted user",
        group_id=s.group_id,
        group_name=group.name if group else None,
        total_amount=s.total_amount,
        split_type=s.split_type,
        note=s.note,
        status=s.status,
        remainder_bearer_username=bearer.username if bearer else None,
        created_at=s.created_at,
        expires_at=s.expires_at,
        locked_at=s.locked_at,
        participants=participants_resp,
        user_share_status=user_status,
        user_share_amount=user_share,
    )


@router.post("", response_model=SplitResponse, status_code=status.HTTP_201_CREATED)
def create_split(
    payload: SplitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new bill split (FR-060 - FR-064).
    The bill is recorded as an expense of the full amount for the payer at creation.
    Requires sufficient wallet balance.
    """
    now = datetime.now(timezone.utc)
    today = get_current_ist_date()

    # 1. Resolve participants based on ad-hoc vs group
    participants_info = []

    if payload.group_id is not None:
        # Group split: goes to all active members of the group (FR-063)
        group = db.scalar(select(Group).where(Group.id == payload.group_id))
        if not group:
            raise AppException(status_code=status.HTTP_404_NOT_FOUND, code="GROUP_NOT_FOUND", message="Group not found.")

        # Check payer active membership
        is_member = db.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group.id,
                GroupMember.user_id == current_user.id,
                GroupMember.status == "active",
            )
        )
        if not is_member:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="NOT_GROUP_MEMBER",
                message="You must be an active group member to create a group split.",
            )

        active_members = db.scalars(
            select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.status == "active")
        ).all()
        member_ids = [m.user_id for m in active_members]
        users = db.scalars(select(User).where(User.id.in_(member_ids))).all()
        user_map = {u.id: u for u in users}

        # Build participant info list
        input_map = {p.username.lower(): p for p in payload.participants}
        for uid in member_ids:
            u = user_map.get(uid)
            if not u:
                continue
            p_input = input_map.get(u.username.lower()) or ParticipantInput(username=u.username, shares=1)
            participants_info.append({
                "user_id": u.id,
                "username": u.username,
                "input": p_input,
            })
    else:
        # Ad-hoc split: validate usernames and check blocking (FR-063, FR-072)
        seen_usernames = set()
        raw_list = list(payload.participants)

        # Ensure payer is in list
        payer_included = any(p.username.strip().lower() == current_user.username for p in raw_list)
        if not payer_included:
            raw_list.append(ParticipantInput(username=current_user.username, shares=1))

        for p_in in raw_list:
            u_name = p_in.username.strip().lower()
            if u_name in seen_usernames:
                continue
            seen_usernames.add(u_name)

            u = db.scalar(select(User).where(User.username == u_name))
            if not u:
                raise AppException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="USER_NOT_FOUND",
                    message=f"User '{u_name}' not found.",
                )

            # Check blocking (FR-072)
            if u.id != current_user.id and is_user_blocked(db, current_user.id, u.id):
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="CANNOT_SPLIT_WITH_USER",
                    message="Unable to create split with one or more specified users.",
                )

            participants_info.append({
                "user_id": u.id,
                "username": u.username,
                "input": p_in,
            })

    # Resolve remainder bearer
    remainder_bearer_id = None
    if payload.remainder_bearer_username:
        b_user = db.scalar(select(User).where(User.username == payload.remainder_bearer_username.strip().lower()))
        if b_user:
            remainder_bearer_id = b_user.id

    # Calculate exact whole-rupee shares
    calculated_shares, final_bearer_id = calculate_participant_shares(
        payload.total_amount,
        payload.split_type,
        participants_info,
        remainder_bearer_id,
    )

    # 2. Check and lock payer wallet
    payer_wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )
    if not payer_wallet:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WALLET_NOT_INITIALIZED",
            message="Please initialize your wallet before creating a bill split.",
        )

    if payer_wallet.current_balance < payload.total_amount:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INSUFFICIENT_FUNDS",
            message=f"Bill total of ₹{payload.total_amount} exceeds wallet balance of ₹{payer_wallet.current_balance}.",
        )

    # Deduct full amount from payer wallet (FR-060)
    payer_wallet.current_balance -= payload.total_amount

    # Resolve category
    if payload.category_id:
        category = db.scalar(select(Category).where(Category.id == payload.category_id, Category.user_id == current_user.id))
    else:
        category = db.scalar(select(Category).where(Category.user_id == current_user.id, Category.name == "Food & Dining"))
        if not category:
            category = db.scalar(select(Category).where(Category.user_id == current_user.id, Category.type == "expense"))

    if not category:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CATEGORY_REQUIRED",
            message="Valid expense category required.",
        )

    # Create payer expense transaction
    payer_tx = Transaction(
        user_id=current_user.id,
        wallet_id=payer_wallet.id,
        type="expense",
        amount=payload.total_amount,
        date=today,
        category_id=category.id,
        payment_method=payload.payment_method,
        note=payload.note or f"Bill split: {payload.split_type}",
        source="split",
        read_only=False,  # amount will decrease as others accept (FR-065)
    )
    db.add(payer_tx)
    db.flush()

    # Create Split
    split_obj = Split(
        payer_id=current_user.id,
        group_id=payload.group_id,
        total_amount=payload.total_amount,
        split_type=payload.split_type,
        note=payload.note.strip() if payload.note else None,
        status="pending",
        remainder_bearer_id=final_bearer_id,
        created_at=now,
        expires_at=now + timedelta(days=7),  # 7-day expiration (FR-067)
    )
    db.add(split_obj)
    db.flush()

    payer_tx.split_id = split_obj.id

    # Create Split Participants
    for item in calculated_shares:
        is_payer = (item["user_id"] == current_user.id)
        part = SplitParticipant(
            split_id=split_obj.id,
            user_id=item["user_id"],
            share_amount=item["share_amount"],
            status="accepted" if is_payer else "pending",
            responded_at=now if is_payer else None,
        )
        db.add(part)

        # Notify non-payer participants (FR-064)
        if not is_payer:
            notif = Notification(
                user_id=item["user_id"],
                type="split_request",
                payload={
                    "message": f"{current_user.username} sent you a split bill request for ₹{item['share_amount']} ({split_obj.note or 'Bill'}).",
                    "split_id": split_obj.id,
                    "share_amount": item["share_amount"],
                    "payer": current_user.username,
                },
                is_read=False,
            )
            db.add(notif)

    check_and_trigger_budget_alerts(db, current_user.id, today)
    db.commit()
    db.refresh(split_obj)

    return _to_split_response(split_obj, current_user.id, db)


@router.get("", response_model=List[SplitResponse])
def list_splits(
    filter_type: Optional[str] = Query(None, pattern="^(all|created|participating)$"),
    status_filter: Optional[str] = Query(None, pattern="^(pending|locked|cancelled)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List splits with status, including participation and lazy expiry (FR-067, FR-070)."""
    now = datetime.now(timezone.utc)

    # Base query
    stmt = (
        select(Split)
        .outerjoin(SplitParticipant, SplitParticipant.split_id == Split.id)
        .where(or_(Split.payer_id == current_user.id, SplitParticipant.user_id == current_user.id))
        .distinct()
        .order_by(desc(Split.created_at))
    )

    if filter_type == "created":
        stmt = stmt.where(Split.payer_id == current_user.id)
    elif filter_type == "participating":
        stmt = stmt.where(Split.payer_id != current_user.id)

    if status_filter:
        stmt = stmt.where(Split.status == status_filter)

    splits = db.scalars(stmt).all()

    # Lazy expiration check on access (FR-067)
    changed = False
    for s in splits:
        if s.status != "cancelled" and ensure_utc(s.expires_at) <= now:
            for p in s.participants:
                if p.status == "pending":
                    p.status = "expired"
                    p.responded_at = now
                    changed = True
    if changed:
        db.commit()

    return [_to_split_response(s, current_user.id, db) for s in splits]


@router.get("/{split_id}", response_model=SplitResponse)
def get_split(
    split_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed split information scoped to payer or participant."""
    now = datetime.now(timezone.utc)
    split_obj = db.scalar(select(Split).where(Split.id == split_id))
    if not split_obj:
        raise AppException(status_code=status.HTTP_404_NOT_FOUND, code="SPLIT_NOT_FOUND", message="Split not found.")

    is_payer = (split_obj.payer_id == current_user.id)
    part_ids = [p.user_id for p in split_obj.participants]
    if not is_payer and current_user.id not in part_ids:
        raise AppException(status_code=status.HTTP_403_FORBIDDEN, code="NOT_SPLIT_PARTICIPANT", message="Access denied.")

    # Lazy expiry check
    if split_obj.status != "cancelled" and ensure_utc(split_obj.expires_at) <= now:
        changed = False
        for p in split_obj.participants:
            if p.status == "pending":
                p.status = "expired"
                p.responded_at = now
                changed = True
        if changed:
            db.commit()

    return _to_split_response(split_obj, current_user.id, db)


@router.post("/{split_id}/accept", response_model=SplitResponse)
def accept_split_share(
    split_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept split request (FR-065).
    ATOMIC TRANSACTION WITH ROW LOCKING ON BOTH WALLETS:
    1. Participant wallet balance checked (if balance < share, blocked & notified).
    2. Participant debited; read-only 'Shared' expense created.
    3. Payer credited; payer original expense reduced.
    4. Both parties notified.
    5. Split marked locked (FR-068).
    """
    now = datetime.now(timezone.utc)
    today = get_current_ist_date()

    # 1. Lock participant record
    part = db.scalar(
        select(SplitParticipant)
        .where(SplitParticipant.split_id == split_id, SplitParticipant.user_id == current_user.id)
        .with_for_update()
    )
    if not part:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PARTICIPANT_NOT_FOUND",
            message="No participation record found for this split.",
        )

    if part.status != "pending":
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="NOT_PENDING",
            message=f"Split share is already {part.status}.",
        )

    split_obj = db.scalar(select(Split).where(Split.id == split_id).with_for_update())
    if split_obj.status == "cancelled":
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SPLIT_CANCELLED",
            message="This split has been cancelled.",
        )

    # Check 7-day expiry
    if ensure_utc(split_obj.expires_at) <= now:
        part.status = "expired"
        part.responded_at = now
        db.commit()
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SPLIT_EXPIRED",
            message="This split request has expired.",
        )

    # 2. Row-level lock on BOTH wallets in deterministic order to prevent deadlocks (NFR-010)
    user_ids = sorted([current_user.id, split_obj.payer_id])
    locked_wallets = db.scalars(
        select(Wallet).where(Wallet.user_id.in_(user_ids)).order_by(Wallet.id.asc()).with_for_update()
    ).all()
    wallet_by_user = {w.user_id: w for w in locked_wallets}

    part_wallet = wallet_by_user.get(current_user.id)
    payer_wallet = wallet_by_user.get(split_obj.payer_id)

    if not part_wallet or not payer_wallet:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WALLET_NOT_FOUND",
            message="Wallet missing for transaction.",
        )

    # Balance check: if balance < share, accept is blocked (FR-065 step 1)
    if part_wallet.current_balance < part.share_amount:
        notif = Notification(
            user_id=current_user.id,
            type="accept_blocked",
            payload={
                "message": f"Unable to accept split for '{split_obj.note or 'Bill'}': insufficient balance (need ₹{part.share_amount}, have ₹{part_wallet.current_balance}).",
                "split_id": split_obj.id,
            },
            is_read=False,
        )
        db.add(notif)
        db.commit()
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INSUFFICIENT_FUNDS",
            message=f"Insufficient balance (need ₹{part.share_amount}, have ₹{part_wallet.current_balance}).",
        )

    # 3. Debit participant wallet and credit payer wallet
    part_wallet.current_balance -= part.share_amount
    payer_wallet.current_balance += part.share_amount

    # 4. Find participant's protected "Shared" expense category
    shared_cat = db.scalar(
        select(Category).where(
            Category.user_id == current_user.id,
            Category.name == "Shared",
            Category.type == "expense",
        )
    )
    if not shared_cat:
        # Fallback to any expense category if shared somehow missing
        shared_cat = db.scalar(select(Category).where(Category.user_id == current_user.id, Category.type == "expense"))

    # Create participant's read-only "Shared" expense
    part_tx = Transaction(
        user_id=current_user.id,
        wallet_id=part_wallet.id,
        type="expense",
        amount=part.share_amount,
        date=today,
        category_id=shared_cat.id,
        payment_method="UPI",
        note=f"Split share: {split_obj.note or 'Bill'}",
        source="split",
        split_id=split_obj.id,
        read_only=True,  # Read-only per FR-027
    )
    db.add(part_tx)

    # Reduce payer's original transaction amount
    payer_tx = db.scalar(
        select(Transaction).where(
            Transaction.split_id == split_obj.id,
            Transaction.user_id == split_obj.payer_id,
        )
    )
    if payer_tx:
        payer_tx.amount -= part.share_amount

    # 5. Update participant and split status
    part.status = "accepted"
    part.responded_at = now

    split_obj.status = "locked"  # Locks upon first acceptance (FR-068)
    if not split_obj.locked_at:
        split_obj.locked_at = now

    # 6. Notifications for both parties
    payer = db.scalar(select(User).where(User.id == split_obj.payer_id))
    notif_payer = Notification(
        user_id=split_obj.payer_id,
        type="split_accepted",
        payload={
            "message": f"{current_user.username} accepted their share of ₹{part.share_amount} for '{split_obj.note or 'Bill'}'. Your bill was reduced by ₹{part.share_amount}.",
            "split_id": split_obj.id,
            "share_amount": part.share_amount,
        },
        is_read=False,
    )
    db.add(notif_payer)

    notif_part = Notification(
        user_id=current_user.id,
        type="split_accepted",
        payload={
            "message": f"You accepted split share of ₹{part.share_amount} for '{split_obj.note or 'Bill'}'. ₹{part.share_amount} debited from your wallet.",
            "split_id": split_obj.id,
            "share_amount": part.share_amount,
        },
        is_read=False,
    )
    db.add(notif_part)

    # Trigger budget alerts for participant
    check_and_trigger_budget_alerts(db, current_user.id, today)

    db.commit()
    db.refresh(split_obj)
    return _to_split_response(split_obj, current_user.id, db)


@router.post("/{split_id}/reject", response_model=SplitResponse)
def reject_split_share(
    split_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reject split share (FR-066).
    No money moves; share stays with payer. Payer receives notification.
    """
    now = datetime.now(timezone.utc)
    part = db.scalar(
        select(SplitParticipant)
        .where(SplitParticipant.split_id == split_id, SplitParticipant.user_id == current_user.id)
    )
    if not part:
        raise AppException(status_code=status.HTTP_404_NOT_FOUND, code="PARTICIPANT_NOT_FOUND", message="Participant not found.")

    if part.status != "pending":
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="NOT_PENDING",
            message=f"Split share is already {part.status}.",
        )

    split_obj = db.scalar(select(Split).where(Split.id == split_id))
    part.status = "rejected"
    part.responded_at = now

    notif = Notification(
        user_id=split_obj.payer_id,
        type="split_rejected",
        payload={
            "message": f"{current_user.username} rejected their share of ₹{part.share_amount} for '{split_obj.note or 'Bill'}'.",
            "split_id": split_obj.id,
            "share_amount": part.share_amount,
        },
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(split_obj)

    return _to_split_response(split_obj, current_user.id, db)


@router.delete("/{split_id}", status_code=status.HTTP_200_OK)
def cancel_split(
    split_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel split (FR-068).
    Allowed ONLY while NO participant has accepted.
    Cancels split, restores payer wallet, and notifies participants.
    """
    split_obj = db.scalar(select(Split).where(Split.id == split_id, Split.payer_id == current_user.id))
    if not split_obj:
        raise AppException(status_code=status.HTTP_404_NOT_FOUND, code="SPLIT_NOT_FOUND", message="Split not found or you are not payer.")

    if split_obj.status == "locked":
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SPLIT_LOCKED",
            message="Cannot cancel split: one or more participants have already accepted.",
        )

    # Check if any non-payer participant accepted
    any_accepted = any(
        p.status == "accepted" and p.user_id != current_user.id for p in split_obj.participants
    )
    if any_accepted:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SPLIT_LOCKED",
            message="Cannot cancel split: one or more participants have already accepted.",
        )

    split_obj.status = "cancelled"

    # Restore payer wallet and remove/cancel original transaction
    payer_wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )
    payer_tx = db.scalar(
        select(Transaction).where(Transaction.split_id == split_obj.id, Transaction.user_id == current_user.id)
    )
    if payer_tx and payer_wallet:
        payer_wallet.current_balance += payer_tx.amount
        db.delete(payer_tx)

    # Notify participants
    for p in split_obj.participants:
        if p.user_id and p.user_id != current_user.id:
            p.status = "cancelled"
            notif = Notification(
                user_id=p.user_id,
                type="split_cancelled",
                payload={
                    "message": f"Split '{split_obj.note or 'Bill'}' was cancelled by {current_user.username}.",
                    "split_id": split_obj.id,
                },
                is_read=False,
            )
            db.add(notif)

    db.commit()
    return {"message": "Split cancelled successfully and payer funds restored."}
