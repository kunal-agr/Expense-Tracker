from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.category import CategoryResponse, SubcategoryResponse, CategoryCreate, CategoryUpdate
from app.auth.dependencies import get_current_user, get_user_record
from app.errors import AppException

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponse])
def get_categories(
    type: Optional[str] = Query(None, pattern="^(income|expense)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List top-level categories and nested subcategories for the authenticated user (FR-030)."""
    stmt = (
        select(Category)
        .where(Category.user_id == current_user.id, Category.parent_id.is_(None))
        .order_by(Category.name.asc())
    )
    if type:
        stmt = stmt.where(Category.type == type)

    top_categories = db.scalars(stmt).all()

    # Preload all subcategories for user
    sub_stmt = (
        select(Category)
        .where(Category.user_id == current_user.id, Category.parent_id.is_not(None))
        .order_by(Category.name.asc())
    )
    all_subs = db.scalars(sub_stmt).all()
    sub_map = {}
    for sub in all_subs:
        sub_map.setdefault(sub.parent_id, []).append(
            SubcategoryResponse(
                id=sub.id,
                user_id=sub.user_id,
                parent_id=sub.parent_id,
                name=sub.name,
                type=sub.type,
                is_protected=sub.is_protected,
                created_at=sub.created_at,
            )
        )

    response = []
    for cat in top_categories:
        response.append(
            CategoryResponse(
                id=cat.id,
                user_id=cat.user_id,
                parent_id=cat.parent_id,
                name=cat.name,
                type=cat.type,
                is_protected=cat.is_protected,
                created_at=cat.created_at,
                subcategories=sub_map.get(cat.id, []),
            )
        )
    return response


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new category or subcategory (FR-030). Enforces max 1 level of nesting."""
    parent_id = payload.parent_id
    if parent_id is not None:
        parent = get_user_record(db, Category, current_user.id, parent_id, "PARENT_NOT_FOUND", "Parent category not found.")
        if parent.parent_id is not None:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="MAX_NESTING_EXCEEDED",
                message="Subcategories cannot be nested more than one level deep.",
            )
        if parent.type != payload.type:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="TYPE_MISMATCH",
                message=f"Subcategory type '{payload.type}' must match parent category type '{parent.type}'.",
            )

    category = Category(
        user_id=current_user.id,
        parent_id=parent_id,
        name=payload.name.strip(),
        type=payload.type,
        is_protected=False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    return CategoryResponse(
        id=category.id,
        user_id=category.user_id,
        parent_id=category.parent_id,
        name=category.name,
        type=category.type,
        is_protected=category.is_protected,
        created_at=category.created_at,
        subcategories=[],
    )


@router.patch("/{category_id}", response_model=CategoryResponse)
def rename_category(
    category_id: int,
    payload: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename category (FR-031, FR-032). 'Shared' cannot be renamed."""
    category = get_user_record(db, Category, current_user.id, category_id, "CATEGORY_NOT_FOUND", "Category not found.")

    if category.is_protected and category.name == "Shared":
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="PROTECTED_CATEGORY_RENAME",
            message="The protected 'Shared' category cannot be renamed.",
        )

    category.name = payload.name.strip()
    db.commit()
    db.refresh(category)

    # Fetch subcategories if top level
    subs = db.scalars(
        select(Category).where(Category.user_id == current_user.id, Category.parent_id == category.id)
    ).all()

    return CategoryResponse(
        id=category.id,
        user_id=category.user_id,
        parent_id=category.parent_id,
        name=category.name,
        type=category.type,
        is_protected=category.is_protected,
        created_at=category.created_at,
        subcategories=[
            SubcategoryResponse(
                id=s.id,
                user_id=s.user_id,
                parent_id=s.parent_id,
                name=s.name,
                type=s.type,
                is_protected=s.is_protected,
                created_at=s.created_at,
            )
            for s in subs
        ],
    )


@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete category (FR-031, FR-032).
    Blocked if category is protected ('Shared', 'Other') or if any transaction uses it.
    """
    category = get_user_record(db, Category, current_user.id, category_id, "CATEGORY_NOT_FOUND", "Category not found.")

    if category.is_protected:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="PROTECTED_CATEGORY_DELETE",
            message=f"The protected category '{category.name}' cannot be deleted.",
        )

    # Collect category id and all child subcategory ids
    child_ids = list(
        db.scalars(select(Category.id).where(Category.parent_id == category.id)).all()
    )
    all_target_ids = [category.id] + child_ids

    # Check if any transaction uses any of these categories
    tx_count = db.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.user_id == current_user.id,
            or_(
                Transaction.category_id.in_(all_target_ids),
                Transaction.subcategory_id.in_(all_target_ids),
            ),
        )
    )
    if tx_count and tx_count > 0:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CATEGORY_IN_USE",
            message=f"Cannot delete category: {tx_count} existing transaction(s) are linked to it.",
        )

    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully."}
