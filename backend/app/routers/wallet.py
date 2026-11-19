from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.wallet import OpeningBalanceRequest, WalletResponse
from app.auth.dependencies import get_current_user
from app.services.category_seeder import seed_default_categories
from app.errors import AppException

router = APIRouter(tags=["Wallet"])


@router.get("/wallet", response_model=WalletResponse)
def get_user_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the current user's wallet and balance (FR-020 - FR-022)."""
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == current_user.id))
    if not wallet:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="WALLET_NOT_FOUND",
            message="Wallet has not been initialized. Please set up your opening balance first.",
        )
    return wallet


@router.put("/me/opening-balance", response_model=WalletResponse)
def set_or_edit_opening_balance(
    payload: OpeningBalanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set opening balance on first setup (FR-009) or edit later (FR-010).
    Minimum ₹100 whole rupees.
    Edits shift the current balance by the difference; blocked if balance would become negative.
    """
    # Use row-level locking for money-moving operations (NFR-010)
    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )

    if not wallet:
        # First-time setup (FR-009)
        wallet = Wallet(
            user_id=current_user.id,
            opening_balance=payload.opening_balance,
            current_balance=payload.opening_balance,
        )
        db.add(wallet)
        # Seed default categories for new user
        seed_default_categories(db, current_user.id)
        db.commit()
        db.refresh(wallet)
        return wallet

    # Editing existing opening balance (FR-010)
    diff = payload.opening_balance - wallet.opening_balance
    new_balance = wallet.current_balance + diff

    if new_balance < 0:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_BALANCE_EDIT",
            message=f"Editing opening balance by {diff} would make current balance negative (₹{new_balance}).",
        )

    wallet.opening_balance = payload.opening_balance
    wallet.current_balance = new_balance
    db.commit()
    db.refresh(wallet)
    return wallet
