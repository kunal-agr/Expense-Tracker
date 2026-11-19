from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.category import Category
from app.models.transaction import Transaction
from app.auth.dependencies import get_current_user
from app.services.export_service import export_to_csv, export_to_xlsx, export_to_pdf
from app.errors import AppException

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/transactions")
def export_transactions(
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$", description="Export file format"),
    from_date: Optional[date] = Query(None, alias="from", description="Start date filter (inclusive)"),
    to_date: Optional[date] = Query(None, alias="to", description="End date filter (inclusive)"),
    category_id: Optional[int] = Query(None, alias="category", description="Category ID filter"),
    type: Optional[str] = Query(None, pattern="^(income|expense)$", description="Type filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export transactions as CSV, Excel (.xlsx), or PDF (FR-091 - FR-094).
    Contains only requesting user's data. Supports date range, category, and type filters.
    """
    stmt = (
        select(Transaction, Category.name.label("category_name"))
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == current_user.id)
    )

    if from_date:
        stmt = stmt.where(Transaction.date >= from_date)
    if to_date:
        stmt = stmt.where(Transaction.date <= to_date)
    if category_id:
        stmt = stmt.where(
            or_(
                Transaction.category_id == category_id,
                Transaction.subcategory_id == category_id,
            )
        )
    if type:
        stmt = stmt.where(Transaction.type == type)

    stmt = stmt.order_by(desc(Transaction.date), desc(Transaction.id))
    results = db.execute(stmt).all()

    # Preload subcategories
    sub_ids = [r[0].subcategory_id for r in results if r[0].subcategory_id]
    sub_map = {}
    if sub_ids:
        subs = db.scalars(select(Category).where(Category.id.in_(sub_ids))).all()
        sub_map = {s.id: s.name for s in subs}

    tx_data = []
    total_income = 0
    total_expense = 0

    for tx, cat_name in results:
        if tx.type == "income":
            total_income += tx.amount
        else:
            total_expense += tx.amount

        tx_data.append({
            "id": tx.id,
            "date": tx.date,
            "type": tx.type,
            "category_name": cat_name,
            "subcategory_name": sub_map.get(tx.subcategory_id),
            "payment_method": tx.payment_method,
            "note": tx.note,
            "source": tx.source,
            "amount": tx.amount,
        })

    summary = {
        "count": len(tx_data),
        "total_income": total_income,
        "total_expense": total_expense,
        "net": total_income - total_expense,
    }

    date_str = datetime.now().strftime("%Y%m%d")

    if format == "csv":
        content = export_to_csv(tx_data)
        media_type = "text/csv; charset=utf-8"
        filename = f"transactions_{date_str}.csv"
    elif format == "xlsx":
        content = export_to_xlsx(tx_data, summary)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"transactions_{date_str}.xlsx"
    elif format == "pdf":
        content = export_to_pdf(tx_data, summary, current_user.username)
        media_type = "application/pdf"
        filename = f"transactions_{date_str}.pdf"
    else:
        raise AppException(status_code=status.HTTP_400_BAD_REQUEST, code="INVALID_FORMAT", message="Unsupported export format.")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
