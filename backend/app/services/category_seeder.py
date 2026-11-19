from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.category import Category


STARTER_EXPENSE_CATEGORIES = [
    {
        "name": "Food & Dining",
        "subcategories": ["Groceries", "Restaurants", "Snacks & Cafe"],
    },
    {
        "name": "Transport",
        "subcategories": ["Fuel", "Public Transport", "Cab/Auto"],
    },
    {
        "name": "Housing",
        "subcategories": ["Rent", "Maintenance", "Electricity/Water/Gas"],
    },
    {
        "name": "Bills & Recharge",
        "subcategories": ["Mobile", "Internet", "DTH"],
    },
    {
        "name": "Shopping",
        "subcategories": ["Clothing", "Electronics", "Household"],
    },
    {
        "name": "Health",
        "subcategories": ["Medical", "Pharmacy", "Fitness"],
    },
    {
        "name": "Entertainment",
        "subcategories": ["Movies", "Subscriptions", "Games"],
    },
    {"name": "Education", "subcategories": []},
    {"name": "Travel", "subcategories": []},
    {"name": "Personal Care", "subcategories": []},
    {"name": "EMI/Loans", "subcategories": []},
    {"name": "Insurance", "subcategories": []},
    {"name": "Gifts & Donations", "subcategories": []},
    {"name": "Shared", "subcategories": [], "is_protected": True},
    {"name": "Other", "subcategories": [], "is_protected": True},
]

STARTER_INCOME_CATEGORIES = [
    {"name": "Salary", "subcategories": []},
    {"name": "Freelance", "subcategories": []},
    {"name": "Business", "subcategories": []},
    {"name": "Investments", "subcategories": []},
    {"name": "Gift", "subcategories": []},
    {"name": "Refund", "subcategories": []},
    {"name": "Other", "subcategories": [], "is_protected": True},
]


def seed_default_categories(db: Session, user_id: int) -> None:
    """Seed default starter categories for a new user (Appendix A, FR-030, FR-032)."""
    # Check if categories already seeded
    existing_count = db.scalar(
        select(Category.id).where(Category.user_id == user_id).limit(1)
    )
    if existing_count is not None:
        return

    # Seed Expense categories
    for cat_data in STARTER_EXPENSE_CATEGORIES:
        parent = Category(
            user_id=user_id,
            name=cat_data["name"],
            type="expense",
            is_protected=cat_data.get("is_protected", False),
        )
        db.add(parent)
        db.flush()  # populate parent.id

        for sub_name in cat_data["subcategories"]:
            sub = Category(
                user_id=user_id,
                parent_id=parent.id,
                name=sub_name,
                type="expense",
                is_protected=False,
            )
            db.add(sub)

    # Seed Income categories
    for cat_data in STARTER_INCOME_CATEGORIES:
        cat = Category(
            user_id=user_id,
            name=cat_data["name"],
            type="income",
            is_protected=cat_data.get("is_protected", False),
        )
        db.add(cat)

    db.flush()
