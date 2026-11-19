import os
import sys
import uuid
from datetime import datetime, date, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.limiter import limiter
limiter.enabled = False
from app.main import app
from sqlalchemy import select
from app.database import SessionLocal
from app.models.user import User
from app.models.wallet import Wallet
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.budget import Budget
from app.models.goal import Goal
from app.models.recurring import RecurringRule, RecurringRun
from app.models.split import Split, SplitParticipant
from app.models.group import Group, GroupMember
from app.models.block import Block
from app.models.notification import Notification

client = TestClient(app)


def create_test_user(prefix: str = "u", opening_balance: int = 10000) -> dict:
    """Helper to create a fresh user with a wallet and return auth headers and user info."""
    uid = uuid.uuid4().hex[:8]
    username = f"{prefix}_{uid}"
    email = f"{username}@test.com"
    password = "Password123!"

    # 1. Register
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert reg_res.status_code == 201, f"Register failed: {reg_res.text}"
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = reg_res.json()["user"]["id"]

    # 2. Setup wallet
    if opening_balance >= 100:
        bal_res = client.put(
            "/api/v1/me/opening-balance",
            json={"opening_balance": opening_balance},
            headers=headers,
        )
        assert bal_res.status_code == 200, f"Wallet setup failed: {bal_res.text}"

    # 3. Get starter categories
    cats_res = client.get("/api/v1/categories", headers=headers)
    cats = cats_res.json()
    expense_cats = [c for c in cats if c["name"] != "Income"]
    income_cats = [c for c in cats if c["name"] == "Income" or "salary" in c["name"].lower()]

    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "password": password,
        "headers": headers,
        "categories": cats,
        "expense_cat_id": expense_cats[0]["id"] if expense_cats else cats[0]["id"],
    }


# ============================================================================
# Section 1: Check 1.15 & Section 13: Check 13.5 - Cross-User Data Isolation
# ============================================================================
def test_1_15_cross_user_data_isolation():
    user_a = create_test_user("user_a", 10000)
    user_b = create_test_user("user_b", 10000)

    # User A creates a transaction
    tx_res = client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": 500,
            "category_id": user_a["expense_cat_id"],
            "date": str(date.today()),
            "payment_method": "UPI",
            "note": "User A Private Tx",
        },
        headers=user_a["headers"],
    )
    assert tx_res.status_code == 201
    tx_a_id = tx_res.json()["id"]

    # User A creates a savings goal
    goal_res = client.post(
        "/api/v1/goals",
        json={"name": "User A Private Goal", "target_amount": 5000},
        headers=user_a["headers"],
    )
    assert goal_res.status_code == 201
    goal_a_id = goal_res.json()["id"]

    # User A creates a budget
    b_res = client.put(
        "/api/v1/budgets/overall",
        json={"amount": 8000},
        headers=user_a["headers"],
    )
    assert b_res.status_code == 200

    cb_res = client.put(
        f"/api/v1/budgets/categories/{user_a['expense_cat_id']}",
        json={"amount": 3000},
        headers=user_a["headers"],
    )
    assert cb_res.status_code == 200

    # User B attempts to access User A's transaction
    get_tx = client.get(f"/api/v1/transactions/{tx_a_id}", headers=user_b["headers"])
    assert get_tx.status_code in [403, 404], f"Expected 403/404, got {get_tx.status_code}"

    patch_tx = client.patch(
        f"/api/v1/transactions/{tx_a_id}",
        json={"note": "Hacked"},
        headers=user_b["headers"],
    )
    assert patch_tx.status_code in [403, 404], f"Expected 403/404, got {patch_tx.status_code}"

    del_tx = client.delete(f"/api/v1/transactions/{tx_a_id}", headers=user_b["headers"])
    assert del_tx.status_code in [403, 404], f"Expected 403/404, got {del_tx.status_code}"

    # User B attempts to access User A's goal
    get_goal = client.get(f"/api/v1/goals/{goal_a_id}", headers=user_b["headers"])
    assert get_goal.status_code in [403, 404], f"Expected 403/404, got {get_goal.status_code}"

    contrib_goal = client.post(
        f"/api/v1/goals/{goal_a_id}/contribute",
        json={"amount": 100},
        headers=user_b["headers"],
    )
    assert contrib_goal.status_code in [403, 404], f"Expected 403/404, got {contrib_goal.status_code}"

    # User B attempts to delete User A's category budget
    del_cb = client.delete(
        f"/api/v1/budgets/categories/{user_a['expense_cat_id']}",
        headers=user_b["headers"],
    )
    # User B does not have this category budget, so it should 404
    assert del_cb.status_code in [403, 404], f"Expected 403/404, got {del_cb.status_code}"

    print("[PASS] Section 1 Check 1.15 & Section 13 Check 13.5: Data isolation strictly enforced.")


# ============================================================================
# Section 3: Check 3.6 & 3.7 - Negative Balance Invariant Protection
# ============================================================================
def test_3_6_and_3_7_negative_balance_protection():
    u = create_test_user("neg_bal", 1000)  # balance = 1000

    # Add expense of 500 -> balance becomes 500
    tx1 = client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": 500,
            "category_id": u["expense_cat_id"],
            "date": str(date.today()),
            "payment_method": "UPI",
            "note": "Expense 500",
        },
        headers=u["headers"],
    ).json()

    # 3.6: Edit expense amount up to 1501 -> would make balance -1 -> MUST BE BLOCKED
    patch_res = client.patch(
        f"/api/v1/transactions/{tx1['id']}",
        json={"amount": 1501},
        headers=u["headers"],
    )
    assert patch_res.status_code == 400, f"Expected 400, got {patch_res.status_code}"
    assert "INSUFFICIENT_FUNDS" in patch_res.text or "negative" in patch_res.text.lower()

    # Verify balance was NOT mutated
    w = client.get("/api/v1/wallet", headers=u["headers"]).json()
    assert w["current_balance"] == 500

    # Add income of 1000 -> balance becomes 1500
    inc_cat = [c for c in u["categories"] if c.get("type") == "income" or c["name"] == "Salary" or c["name"] == "Other Income"]
    inc_cat_id = inc_cat[0]["id"] if inc_cat else u["expense_cat_id"]
    inc_tx = client.post(
        "/api/v1/transactions",
        json={
            "type": "income",
            "amount": 1000,
            "category_id": inc_cat_id,
            "date": str(date.today()),
            "payment_method": "UPI",
            "note": "Income 1000",
        },
        headers=u["headers"],
    ).json()

    # Add expense of 1200 -> balance becomes 300
    client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": 1200,
            "category_id": u["expense_cat_id"],
            "date": str(date.today()),
            "payment_method": "UPI",
            "note": "Expense 1200",
        },
        headers=u["headers"],
    )

    w = client.get("/api/v1/wallet", headers=u["headers"]).json()
    assert w["current_balance"] == 300

    # 3.7: Delete the 1000 income -> would make balance 300 - 1000 = -700 -> MUST BE BLOCKED
    del_inc = client.delete(f"/api/v1/transactions/{inc_tx['id']}", headers=u["headers"])
    assert del_inc.status_code == 400, f"Expected 400, got {del_inc.status_code}"

    # Also test editing opening balance down below allowable difference (FR-010)
    # Opening balance is 1000, current balance is 300. Lowering opening balance to 500 would reduce balance by 500 -> 300 - 500 = -200 -> BLOCKED
    edit_ob = client.put(
        "/api/v1/me/opening-balance",
        json={"opening_balance": 500},
        headers=u["headers"],
    )
    assert edit_ob.status_code == 400, f"Expected 400, got {edit_ob.status_code}"

    print("[PASS] Section 3 Check 3.6 & 3.7: Balance non-negative invariant enforced on edit, delete, and opening balance.")


# ============================================================================
# Section 4: Check 4.2, 4.4, 4.5 - Categories Lifecycle & Deletion Guard
# ============================================================================
def test_4_categories_lifecycle():
    u = create_test_user("cat_user", 5000)

    # 4.2: Create custom root category
    c_res = client.post(
        "/api/v1/categories",
        json={"name": "Hobbies", "type": "expense"},
        headers=u["headers"],
    )
    assert c_res.status_code == 201
    parent_id = c_res.json()["id"]

    # Create subcategory
    sub_res = client.post(
        "/api/v1/categories",
        json={"name": "Photography", "parent_id": parent_id, "type": "expense"},
        headers=u["headers"],
    )
    assert sub_res.status_code == 201
    sub_id = sub_res.json()["id"]

    # 4.4: Delete subcategory with NO transactions -> SUCCEEDS
    del_sub = client.delete(f"/api/v1/categories/{sub_id}", headers=u["headers"])
    assert del_sub.status_code == 200

    # 4.5: Use parent category in a transaction, then attempt to delete -> MUST BE BLOCKED
    client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": 200,
            "category_id": parent_id,
            "date": str(date.today()),
            "payment_method": "Cash",
            "note": "Camera gear",
        },
        headers=u["headers"],
    )

    del_parent = client.delete(f"/api/v1/categories/{parent_id}", headers=u["headers"])
    assert del_parent.status_code == 400, f"Expected 400, got {del_parent.status_code}"
    assert "CATEGORY_IN_USE" in del_parent.text or "transaction" in del_parent.text.lower()

    print("[PASS] Section 4 Check 4.2, 4.4, 4.5: Category nesting and in-use deletion protection verified.")


# ============================================================================
# Section 5: Budgets (5.1, 5.3, 5.4, 5.6, 5.8, 5.9, 5.12)
# ============================================================================
def test_5_budgets():
    u = create_test_user("budget_user", 50000)

    # 5.1: Try to set category budget BEFORE overall budget exists -> MUST BE BLOCKED
    cat_id = u["expense_cat_id"]
    cb_fail = client.put(
        f"/api/v1/budgets/categories/{cat_id}",
        json={"amount": 5000},
        headers=u["headers"],
    )
    assert cb_fail.status_code == 400, f"Expected 400, got {cb_fail.status_code}"
    assert "OVERALL_BUDGET_NOT_SET" in cb_fail.text or "overall" in cb_fail.text.lower()

    # Set overall budget = 10,000
    ob_res = client.put(
        "/api/v1/budgets/overall",
        json={"amount": 10000},
        headers=u["headers"],
    )
    assert ob_res.status_code == 200

    # Set category budget = 7,000
    cb1 = client.put(
        f"/api/v1/budgets/categories/{cat_id}",
        json={"amount": 7000},
        headers=u["headers"],
    )
    assert cb1.status_code == 200

    # 5.3: Try to set another category budget of 4,000 (total 11,000 > 10,000) -> MUST BE BLOCKED
    other_cats = [c for c in u["categories"] if c["id"] != cat_id and c.get("type") == "expense"]
    other_cat_id = other_cats[0]["id"] if other_cats else u["categories"][1]["id"]
    cb2 = client.put(
        f"/api/v1/budgets/categories/{other_cat_id}",
        json={"amount": 4000},
        headers=u["headers"],
    )
    assert cb2.status_code == 400, f"Expected 400, got {cb2.status_code}"
    assert "BUDGET_EXCEEDS_OVERALL" in cb2.text or "exceed" in cb2.text.lower()

    # 5.4: Try to lower overall budget to 6,000 (below category budget of 7,000) -> MUST BE BLOCKED
    ob_lower = client.put(
        "/api/v1/budgets/overall",
        json={"amount": 6000},
        headers=u["headers"],
    )
    assert ob_lower.status_code == 400, f"Expected 400, got {ob_lower.status_code}"
    assert "BUDGET_BELOW_CATEGORIES" in ob_lower.text or "sum of category" in ob_lower.text.lower()

    # 5.6: 100% threshold allows the expense, does NOT block
    # Spend 10,500 (crossing 100% of 10,000) -> Expense MUST SUCCEED
    exp_res = client.post(
        "/api/v1/transactions",
        json={
            "type": "expense",
            "amount": 10500,
            "category_id": cat_id,
            "date": str(date.today()),
            "payment_method": "UPI",
            "note": "Big expense crossing 100%",
        },
        headers=u["headers"],
    )
    assert exp_res.status_code == 201, f"Expected 201, got {exp_res.status_code}"

    # Status shows > 100%
    curr_month = date.today().strftime("%Y-%m")
    status_res = client.get(f"/api/v1/budgets/status?month={curr_month}", headers=u["headers"]).json()
    assert status_res["overall"]["percentage"] >= 100.0

    # 5.12: Goal contributions do NOT count as budget spending
    status_before = client.get(f"/api/v1/budgets/status?month={curr_month}", headers=u["headers"]).json()
    spent_before = status_before["overall"]["spent"]

    g_res = client.post(
        "/api/v1/goals",
        json={"name": "Goal Check", "target_amount": 5000},
        headers=u["headers"],
    ).json()

    client.post(
        f"/api/v1/goals/{g_res['id']}/contribute",
        json={"amount": 2000},
        headers=u["headers"],
    )

    status_after = client.get(f"/api/v1/budgets/status?month={curr_month}", headers=u["headers"]).json()
    assert status_after["overall"]["spent"] == spent_before, "Goal contribution counted towards budget spending!"

    # 5.8 & 5.9: Carry-forward math verification (test directly via budget service or multi-month status)
    from app.services.budget_service import calculate_effective_overall_budget
    db = SessionLocal()
    try:
        # Create user with 2 past months in DB
        u2 = create_test_user("carry_user", 50000)
        # Set base budget for user
        client.put("/api/v1/budgets/overall", json={"amount": 10000}, headers=u2["headers"])

        # Set effective_from on budget to 2026-09
        b_rec = db.scalar(select(Budget).where(Budget.user_id == u2["user_id"], Budget.scope == "overall"))
        b_rec.effective_from = "2026-09"
        db.commit()

        # Test case 1 (5.8): Month 1 spent 6,000 -> Month 2 gets 10,000 + 4,000 = 14,000
        # Insert transaction in 2026-09
        db.add(Transaction(
            user_id=u2["user_id"],
            wallet_id=db.scalar(select(Wallet.id).where(Wallet.user_id == u2["user_id"])),
            type="expense",
            amount=6000,
            date=date(2026, 9, 15),
            category_id=u2["expense_cat_id"],
            payment_method="UPI",
            source="manual",
            read_only=False,
        ))
        db.commit()

        st_oct = calculate_effective_overall_budget(db, u2["user_id"], "2026-10")
        assert st_oct["carry_forward"] == 4000
        assert st_oct["effective_budget"] == 14000

        # Test case 2 (5.9): Month 2 overspent 15,000 (> 14,000) -> Month 3 should NOT carry a deficit
        db.add(Transaction(
            user_id=u2["user_id"],
            wallet_id=db.scalar(select(Wallet.id).where(Wallet.user_id == u2["user_id"])),
            type="expense",
            amount=15000,
            date=date(2026, 10, 15),
            category_id=u2["expense_cat_id"],
            payment_method="UPI",
            source="manual",
            read_only=False,
        ))
        db.commit()

        st_nov = calculate_effective_overall_budget(db, u2["user_id"], "2026-11")
        assert st_nov["carry_forward"] == 0, f"Expected 0 carry forward, got {st_nov['carry_forward']}"
        assert st_nov["effective_budget"] == 10000, f"Expected 10000 effective budget, got {st_nov['effective_budget']}"

    finally:
        db.close()

    print("[PASS] Section 5 Budgets (5.1, 5.3, 5.4, 5.6, 5.8, 5.9, 5.12) completely verified.")


# ============================================================================
# Section 6: Goals (6.2)
# ============================================================================
def test_6_goals():
    u = create_test_user("goal_user", 500)  # wallet balance = 500
    g = client.post(
        "/api/v1/goals",
        json={"name": "New Phone", "target_amount": 20000},
        headers=u["headers"],
    ).json()

    # 6.2: Try to contribute 600 with balance 500 -> MUST BE BLOCKED
    res = client.post(
        f"/api/v1/goals/{g['id']}/contribute",
        json={"amount": 600},
        headers=u["headers"],
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "INSUFFICIENT_FUNDS" in res.text or "balance" in res.text.lower()

    # Contribute 500 -> SUCCEEDS, balance becomes 0
    res_ok = client.post(
        f"/api/v1/goals/{g['id']}/contribute",
        json={"amount": 500},
        headers=u["headers"],
    )
    assert res_ok.status_code == 200
    w = client.get("/api/v1/wallet", headers=u["headers"]).json()
    assert w["current_balance"] == 0

    print("[PASS] Section 6 Goals Check 6.2: Insufficient funds check verified.")


# ============================================================================
# Section 7: Recurring (7.3, 7.8)
# ============================================================================
def test_7_recurring():
    u = create_test_user("rec_user", 200)  # balance = 200

    # Create monthly recurring rule for 500 on day 1
    rule_res = client.post(
        "/api/v1/recurring",
        json={
            "type": "expense",
            "amount": 500,
            "category_id": u["expense_cat_id"],
            "payment_method": "UPI",
            "note": "Rent SIP",
            "day_of_month": 1,
            "start_date": str(date.today() - timedelta(days=60)),
        },
        headers=u["headers"],
    )
    assert rule_res.status_code == 201
    rule_id = rule_res.json()["id"]

    # 7.3: Catch-up run: wallet has 200 < 500 -> occurrence must be SKIPPED with notification, balance unchanged
    from app.services.recurring_service import apply_recurring_for_user
    db = SessionLocal()
    try:
        runs_count = apply_recurring_for_user(db, u["user_id"])
        db.commit()

        # Balance remains 200
        w = db.scalar(select(Wallet).where(Wallet.user_id == u["user_id"]))
        assert w.current_balance == 200

        # Check notification generated for skipped run
        notif = db.scalar(
            select(Notification).where(
                Notification.user_id == u["user_id"],
                Notification.type == "recurring_skipped",
            )
        )
        assert notif is not None, "Expected recurring_skipped notification"

        # 7.8: Idempotency test: Give user 5000 balance, run catch-up again
        w.current_balance = 5000
        db.commit()

        runs_2 = apply_recurring_for_user(db, u["user_id"])
        db.commit()

        # Check that runs weren't duplicated for already skipped/executed periods
        db_runs = db.scalars(
            select(RecurringRun).where(RecurringRun.rule_id == rule_id)
        ).all()
        # Periods / run_dates are unique
        run_dates = [r.run_date for r in db_runs]
        assert len(run_dates) == len(set(run_dates)), f"Duplicate runs created for recurring rule! Dates: {run_dates}"

    finally:
        db.close()

    print("[PASS] Section 7 Recurring 7.3 & 7.8: Skip on low balance and catch-up idempotency verified.")


# ============================================================================
# Section 8: Splits (8.1, 8.5, 8.6, 8.7, 8.8, 8.9, 8.11, 8.12, 8.13)
# ============================================================================
def test_8_splits():
    payer = create_test_user("payer_user", 10000)
    part_b = create_test_user("part_b", 200)  # low balance initially: 200
    part_c = create_test_user("part_c", 5000)

    # 8.1, 8.5, 8.6: Create 3-way split: Total 1200, Exact shares: Payer 400, Part B 400, Part C 400
    sp_res = client.post(
        "/api/v1/splits",
        json={
            "total_amount": 1200,
            "split_type": "exact",
            "category_id": payer["expense_cat_id"],
            "payment_method": "UPI",
            "note": "Dinner bill",
            "participants": [
                {"username": part_b["username"], "amount": 400},
                {"username": part_c["username"], "amount": 400},
            ],
        },
        headers=payer["headers"],
    )
    assert sp_res.status_code == 201, f"Create split failed: {sp_res.text}"
    split_id = sp_res.json()["id"]

    # Payer's wallet was debited the full 1200 upfront (10000 - 1200 = 8800)
    w_payer = client.get("/api/v1/wallet", headers=payer["headers"]).json()
    assert w_payer["current_balance"] == 8800

    # 8.8: Participant B has 200 < 400 share -> Accept MUST BE BLOCKED
    b_acc_fail = client.post(f"/api/v1/splits/{split_id}/accept", headers=part_b["headers"])
    assert b_acc_fail.status_code == 400, f"Expected 400, got {b_acc_fail.status_code}"
    assert "INSUFFICIENT_FUNDS" in b_acc_fail.text or "balance" in b_acc_fail.text.lower()

    # Verify no partial money moved
    w_b = client.get("/api/v1/wallet", headers=part_b["headers"]).json()
    assert w_b["current_balance"] == 200
    w_payer_check = client.get("/api/v1/wallet", headers=payer["headers"]).json()
    assert w_payer_check["current_balance"] == 8800

    # 8.9: Reject test with another split
    sp_rej = client.post(
        "/api/v1/splits",
        json={
            "total_amount": 600,
            "split_type": "exact",
            "category_id": payer["expense_cat_id"],
            "payment_method": "UPI",
            "note": "Coffee split to reject",
            "participants": [
                {"username": part_c["username"], "amount": 300},
            ],
        },
        headers=payer["headers"],
    ).json()

    c_rej = client.post(f"/api/v1/splits/{sp_rej['id']}/reject", headers=part_c["headers"])
    assert c_rej.status_code == 200

    # Payer balance unaffected (payer already paid upfront, rejection keeps full expense with payer)
    w_c = client.get("/api/v1/wallet", headers=part_c["headers"]).json()
    assert w_c["current_balance"] == 5000

    # 8.11 & 8.12: Participant C accepts the first split (share = 400)
    c_acc = client.post(f"/api/v1/splits/{split_id}/accept", headers=part_c["headers"])
    assert c_acc.status_code == 200

    # Part C wallet debited by 400 (5000 - 400 = 4600)
    w_c_after = client.get("/api/v1/wallet", headers=part_c["headers"]).json()
    assert w_c_after["current_balance"] == 4600

    # Payer wallet refunded Part C's share of 400 (8800 - 600 + 400 = 8600)
    w_payer_after = client.get("/api/v1/wallet", headers=payer["headers"]).json()
    assert w_payer_after["current_balance"] == 8600, f"Expected 8600, got {w_payer_after['current_balance']}"

    # Split is now locked (at least one participant accepted) -> Payer CANNOT cancel
    cancel_res = client.post(f"/api/v1/splits/{split_id}/cancel", headers=payer["headers"])
    assert cancel_res.status_code == 400, f"Expected 400, got {cancel_res.status_code}"

    # 8.13: Accepted share creates a read-only "Shared" transaction for Participant C
    txs_c = client.get("/api/v1/transactions", headers=part_c["headers"]).json()["items"]
    split_tx = [t for t in txs_c if t.get("read_only") is True]
    assert len(split_tx) > 0, "No read-only transaction found for accepted split!"
    split_tx_id = split_tx[0]["id"]

    # Editing or deleting this read-only transaction MUST BE BLOCKED (403 Forbidden)
    patch_ro = client.patch(f"/api/v1/transactions/{split_tx_id}", json={"amount": 100}, headers=part_c["headers"])
    assert patch_ro.status_code == 403, f"Expected 403, got {patch_ro.status_code}"
    assert "READ_ONLY_TRANSACTION" in patch_ro.text

    del_ro = client.delete(f"/api/v1/transactions/{split_tx_id}", headers=part_c["headers"])
    assert del_ro.status_code == 403, f"Expected 403, got {del_ro.status_code}"
    assert "READ_ONLY_TRANSACTION" in del_ro.text

    print("[PASS] Section 8 Splits completely verified (atomic balances, rejection, lock invariants, read-only).")


# ============================================================================
# Section 9: Groups (9.2, 9.9)
# ============================================================================
def test_9_groups():
    user_a = create_test_user("grp_a", 5000)
    user_b = create_test_user("grp_b", 5000)
    user_c = create_test_user("grp_c", 5000)

    # 9.2: User A blocks User B
    blk_res = client.post("/api/v1/blocks", json={"username": user_b["username"]}, headers=user_a["headers"])
    assert blk_res.status_code == 201

    # User B creates group and tries to invite User A -> BLOCKED with generic error
    grp_b = client.post("/api/v1/groups", json={"name": "B's Secret Group"}, headers=user_b["headers"]).json()
    inv_res = client.post(f"/api/v1/groups/{grp_b['id']}/invite", json={"username": user_a["username"]}, headers=user_b["headers"])
    assert inv_res.status_code == 400, f"Expected 400, got {inv_res.status_code}"

    # 9.9: Creator succession: User A creates Group, invites B then C
    # First unblock
    client.delete(f"/api/v1/blocks/{user_b['username']}", headers=user_a["headers"])

    grp_a = client.post("/api/v1/groups", json={"name": "Trip Goa"}, headers=user_a["headers"]).json()
    grp_id = grp_a["id"]

    # User A invites B, B accepts
    client.post(f"/api/v1/groups/{grp_id}/invite", json={"username": user_b["username"]}, headers=user_a["headers"])
    client.post(f"/api/v1/groups/{grp_id}/accept", headers=user_b["headers"])

    # User A invites C, C accepts
    client.post(f"/api/v1/groups/{grp_id}/invite", json={"username": user_c["username"]}, headers=user_a["headers"])
    client.post(f"/api/v1/groups/{grp_id}/accept", headers=user_c["headers"])

    # User A leaves group -> Creator MUST pass to earliest-joined member (User B)
    leave_a = client.post(f"/api/v1/groups/{grp_id}/leave", headers=user_a["headers"])
    assert leave_a.status_code == 200

    detail = client.get(f"/api/v1/groups/{grp_id}", headers=user_b["headers"]).json()
    assert detail["creator_username"] == user_b["username"], f"Expected creator to be {user_b['username']}, got {detail['creator_username']}"

    # User B leaves -> Creator passes to User C
    client.post(f"/api/v1/groups/{grp_id}/leave", headers=user_b["headers"])
    detail_c = client.get(f"/api/v1/groups/{grp_id}", headers=user_c["headers"]).json()
    assert detail_c["creator_username"] == user_c["username"]

    # User C leaves -> Group is empty and deleted
    client.post(f"/api/v1/groups/{grp_id}/leave", headers=user_c["headers"])
    get_deleted = client.get(f"/api/v1/groups/{grp_id}", headers=user_c["headers"])
    assert get_deleted.status_code in [403, 404]

    print("[PASS] Section 9 Groups 9.2 & 9.9: Blocking and creator succession verified.")


# ============================================================================
# Section 13: Security (13.4) - Concurrent Split Accept Simulation
# ============================================================================
def test_13_4_concurrent_split_accept():
    payer = create_test_user("conc_payer", 10000)
    part = create_test_user("conc_part", 5000)

    # Create split: Total 1000, 500 each
    sp = client.post(
        "/api/v1/splits",
        json={
            "total_amount": 1000,
            "split_type": "exact",
            "category_id": payer["expense_cat_id"],
            "payment_method": "UPI",
            "note": "Concurrent Test",
            "participants": [{"username": part["username"], "amount": 500}],
        },
        headers=payer["headers"],
    ).json()

    split_id = sp["id"]

    # Simulate two concurrent accept requests using separate threads
    def try_accept():
        # Use a fresh test client / session per thread
        t_client = TestClient(app)
        return t_client.post(f"/api/v1/splits/{split_id}/accept", headers=part["headers"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(try_accept)
        f2 = executor.submit(try_accept)
        res1 = f1.result()
        res2 = f2.result()

    statuses = [res1.status_code, res2.status_code]
    assert 200 in statuses, f"At least one request must succeed, got {statuses}"
    assert 400 in statuses, f"The duplicate request must be rejected with 400, got {statuses}"

    # Verify participant wallet debited EXACTLY ONCE (5000 - 500 = 4500)
    w_part = client.get("/api/v1/wallet", headers=part["headers"]).json()
    assert w_part["current_balance"] == 4500, f"Expected 4500, got {w_part['current_balance']}"

    # Verify payer wallet refunded EXACTLY ONCE (9000 + 500 = 9500)
    w_payer = client.get("/api/v1/wallet", headers=payer["headers"]).json()
    assert w_payer["current_balance"] == 9500, f"Expected 9500, got {w_payer['current_balance']}"

    print("[PASS] Section 13 Security 13.4: Concurrent split acceptance simulated. Zero double-debit, atomic row locking succeeded.")


if __name__ == "__main__":
    test_1_15_cross_user_data_isolation()
    test_3_6_and_3_7_negative_balance_protection()
    test_4_categories_lifecycle()
    test_5_budgets()
    test_6_goals()
    test_7_recurring()
    test_8_splits()
    test_9_groups()
    test_13_4_concurrent_split_accept()
    print("\n=======================================================")
    print("ALL CRITICAL ACCEPTANCE TESTS COMPLETED SUCCESSFULLY!")
    print("=======================================================")
