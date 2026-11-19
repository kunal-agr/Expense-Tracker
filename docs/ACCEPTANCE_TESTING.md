# Acceptance Testing Checklist: Expense Tracker (v1)

How to use this file: go through each test in order (later tests often rely on data created in earlier ones). For each, do the steps, check the actual result against "Expected", and tick ✅ Pass or ❌ Fail. If it fails, write what actually happened in the Notes column so you can report it back precisely. Re-run the whole file after any update the agent makes, not just the section that changed — a fix in one area can silently break another (e.g. a wallet-balance fix can break split math).

Legend: `FR-xxx` / `NFR-xxx` = the requirement ID in `SRS.md`, so you can cite it exactly when reporting a bug.

---

## 0. Pre-flight

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 0.1 | Backend starts locally without errors | Server boots, `/docs` (OpenAPI/Swagger) loads | ✅ | |
| 0.2 | Frontend starts locally without errors | App loads at localhost, no console errors on first paint | ✅ | |
| 0.3 | Alembic migrations run clean on an empty DB | No errors, all tables created | ✅ | |
| 0.4 | `.env.example` exists in both `backend/` and `frontend/`; no real secrets in git | `git log -p` for `.env` shows nothing committed | ✅ | |
| 0.5 | `.gitignore` is present and covers `.env`, `node_modules/`, `__pycache__/`, `venv/`, build output | Check file contents | ✅ | |

---

## 1. Auth & Account (FR-001 to FR-014, NFR-002, NFR-004 to NFR-007)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 1.1 | Register new user (unique email, unique username, password ≥ 6 chars) | Account created, redirected to opening-balance setup | ✅ | |
| 1.2 | Register with an email that's already used | Blocked with a clear error | ✅ | |
| 1.3 | Register with a username that's already used (try different case, e.g. `Alex` vs `alex`) | Blocked — usernames are case-insensitive unique | ✅ | |
| 1.4 | Register with username containing spaces/symbols or < 3 or > 20 chars | Blocked with validation error | ✅ | |
| 1.5 | Register with password < 6 chars | Blocked | ✅ | |
| 1.6 | Login with correct email + password | Success, lands on dashboard | ✅ | |
| 1.7 | Login with correct **username** + password | Success | ✅ | |
| 1.8 | Login with wrong password | Generic error, does **not** reveal whether the account exists (NFR-007) | ✅ | |
| 1.9 | Login 6+ times rapidly with wrong password | Rate limited (HTTP 429) after ~5 attempts/min (NFR-004) | ✅ | |
| 1.10 | Access an app page after access token expires (wait 15+ min or tamper with expiry) but with a valid refresh token | Silently refreshes, stays logged in | ✅ | |
| 1.11 | Logout, then try to reuse the old refresh token | Rejected — session revoked (FR-006, FR-007) | ☐ | |
| 1.12 | Login from two different browsers/devices at once | Both sessions stay active simultaneously (FR-005) | ☐ | |
| 1.13 | "Log out of all devices" from one session | All sessions invalidated, other device gets logged out on its next request | ☐ | |
| 1.14 | Change username, then try logging in with the **old** username | Old username rejected (freed); new username works (FR-008) | ☐ | |
| 1.15 | **Data isolation:** as User A, try to fetch/edit a transaction/goal/budget ID that belongs to User B (e.g. by guessing/incrementing an ID in a request) | Blocked (403/404), never returns B's data (NFR-002) — **critical test, do not skip** | ☐ | |
| 1.16 | Delete account with wrong password confirmation | Blocked | ☐ | |
| 1.17 | Delete account with correct password | Account and personal data gone; username becomes available again; any splits this user was part of now show "Deleted user" to the other party (FR-011) | ☐ | |

---

## 2. Wallet Setup & Opening Balance (FR-009, FR-010, FR-020 to FR-022)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 2.1 | First login — try to skip opening balance setup | Cannot reach the main app without setting it | ☐ | |
| 2.2 | Enter opening balance below ₹100 | Blocked | ☐ | |
| 2.3 | Enter opening balance ≥ ₹100 (whole rupees only; try a decimal) | Accepted only as a whole number; decimal rejected or rounded with a clear rule | ☐ | |
| 2.4 | Check dashboard balance right after setup | Equals the opening balance exactly | ☐ | |
| 2.5 | Edit opening balance later (increase) | Current balance shifts up by the difference; past transactions unchanged | ☐ | |
| 2.6 | Edit opening balance down so it would make current balance negative | Blocked (FR-010) | ☐ | |
| 2.7 | Balance shown uses Indian digit grouping (e.g. ₹1,00,000, not ₹100,000) | FR-021 | ☐ | |

---

## 3. Transactions (FR-023 to FR-028)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 3.1 | Add an expense within balance | Succeeds, balance drops by that amount | ☐ | |
| 3.2 | Add an expense **larger than current balance** | Blocked with a clear message (FR-025) — **critical** | ☐ | |
| 3.3 | Add an income | Succeeds, balance rises | ☐ | |
| 3.4 | Try to set a **future date** on a transaction | Blocked (FR-024) | ☐ | |
| 3.5 | Set a past date | Allowed | ☐ | |
| 3.6 | Edit a transaction's amount up, such that it would push current balance negative | Blocked (FR-026) | ☐ | |
| 3.7 | Delete an income transaction that would make current balance negative | Blocked | ☐ | |
| 3.8 | Edit/delete a transaction that was created from an **accepted split** | Not allowed — fields are read-only / no delete button (FR-027) — **critical, this is a money-integrity rule** | ☐ | |
| 3.9 | Add 15+ transactions, use filters (date range, category, type, payment method) and search by note text | Correct filtered subset returned | ☐ | |
| 3.10 | Sort by date and by amount, check pagination with 20+ records | Correct order, pages don't duplicate or skip rows | ☐ | |
| 3.11 | Payment method field available and saved correctly for both income and expense | FR-023 | ☐ | |

---

## 4. Categories (FR-030 to FR-032)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 4.1 | New user has the full starter category list (Appendix A) pre-seeded | Check against the list | ☐ | |
| 4.2 | Create a custom category and a subcategory under it | Succeeds | ☐ | |
| 4.3 | Rename any category (including one with transactions) | Always allowed (FR-031) | ☐ | |
| 4.4 | Delete a category that has **no** transactions | Succeeds | ☐ | |
| 4.5 | Delete a category that **has** transactions | Blocked | ☐ | |
| 4.6 | Try to delete or rename **"Shared"** | Delete blocked and rename blocked (FR-032) | ☐ | |
| 4.7 | Try to delete **"Other"** (income or expense) | Blocked | ☐ | |

---

## 5. Budgets (FR-040 to FR-047)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 5.1 | Try to set a category budget before any overall budget exists | Blocked (FR-042) | ☐ | |
| 5.2 | Set overall monthly budget, then a category budget within it | Succeeds | ☐ | |
| 5.3 | Try to set category budgets whose sum exceeds the overall budget | Blocked | ☐ | |
| 5.4 | Try to lower the overall budget below the current category-budget sum | Blocked | ☐ | |
| 5.5 | Spend until you cross 80% of the overall budget | In-app notification fires once (not repeatedly) | ☐ | |
| 5.6 | Spend until you cross 100% of the overall budget | Second notification fires; the expense is **still allowed**, not blocked (FR-046) | ☐ | |
| 5.7 | Spend past 100%, then add more expenses in the same month | No repeated 100% notifications for every subsequent expense (FR-045: once per threshold per month) | ☐ | |
| 5.8 | Leave some overall budget unused this month, move to next month | Next month's effective overall budget = base + last month's unused amount (FR-043) | ☐ | |
| 5.9 | Overspend the overall budget this month, move to next month | Next month's budget is just the base amount — no penalty/deduction (FR-046) | ☐ | |
| 5.10 | Cross 80%/100% of a **category** budget specifically | Separate notification from the overall-budget one | ☐ | |
| 5.11 | Check that category budgets do **not** carry forward unused amounts | Next month's category budget = base amount only | ☐ | |
| 5.12 | Contribute to a savings goal — confirm it does **not** count toward budget "spent" | Budget progress unaffected by goal contributions (FR-044) | ☐ | |

---

## 6. Savings Goals (FR-053 to FR-055)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 6.1 | Create a goal with a target amount and deadline | Succeeds | ☐ | |
| 6.2 | Contribute an amount you don't have in your wallet | Blocked (balance rule applies) | ☐ | |
| 6.3 | Contribute within balance | Wallet balance drops, goal progress rises | ☐ | |
| 6.4 | Withdraw part of the goal back to wallet | Wallet balance rises, goal progress drops | ☐ | |
| 6.5 | Contribute enough to hit the target exactly | Goal marked "completed", notification fires | ☐ | |
| 6.6 | Delete a goal that still has saved money in it | Saved amount returns to wallet balance (FR-055) | ☐ | |

---

## 7. Recurring Transactions (FR-048 to FR-052b)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 7.1 | Create a monthly recurring expense/income with a day of month | Rule saved | ☐ | |
| 7.2 | Create a rule with day 29, 30 or 31, test it against a month that doesn't have that day (e.g. Feb) | Falls back to the last day of that month (FR-049) | ☐ | |
| 7.3 | Let a recurring **expense** occurrence trigger when wallet balance is too low | Occurrence skipped for that month, in-app notification explains why (FR-051) — not retried automatically | ☐ | |
| 7.4 | Let a recurring **income** occurrence trigger | Always applies, regardless of balance | ☐ | |
| 7.5 | Pause a rule, then confirm the next scheduled date does not auto-add | No transaction created while paused | ☐ | |
| 7.6 | Resume a paused rule | Future occurrences resume; past paused dates are not retroactively applied | ☐ | |
| 7.7 | Set an end date on a rule in the past | No further occurrences | ☐ | |
| 7.8 | Simulate a missed run (e.g. don't log in for a few days / disable the cron call) then log in | Missed occurrence(s) are caught up in correct chronological order, each applied exactly once (FR-052b — idempotency) | ☐ | |
| 7.9 | Confirm a successful auto-add always produces a notification | FR-052a | ☐ | |

---

## 8. Bill Splitting (FR-060 to FR-071) — highest-risk area, test carefully

Use at least two test accounts (Alex = payer, Alice = participant) for these.

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 8.1 | Alex creates a split for ₹900 equally between Alex, Alice, Jack (3-way) | Alex's wallet debited ₹900 immediately; Alex's expense shows ₹900 **before anyone accepts** (FR-060, FR-066-context) | ☐ | |
| 8.2 | Create a split as exact amounts; amounts don't sum to the bill total | Blocked | ☐ | |
| 8.3 | Create a split as percentages; percentages don't sum to 100 | Blocked | ☐ | |
| 8.4 | Create a split as shares (e.g. 1:1:2) | Correct proportional amounts computed | ☐ | |
| 8.5 | Split an amount that doesn't divide evenly (e.g. ₹100 ÷ 3) | You are asked to choose who bears the ₹1 remainder, before sending (FR-062) | ☐ | |
| 8.6 | Alice **accepts** her ₹300 share | Alice's wallet -₹300, a read-only "Shared" expense of ₹300 appears for Alice; Alex's wallet +₹300; Alex's original expense drops from ₹900 to ₹600; both get notified (FR-065) | ☐ | |
| 8.7 | Jack also accepts his ₹300 share | Alex's expense drops to ₹300; Jack's wallet -₹300 with a "Shared" expense | ☐ | |
| 8.8 | Create a new split, have a participant with **insufficient balance** try to accept | Accept blocked, request stays pending, participant notified about insufficient balance, **no partial money movement** (FR-065 step 1) — **critical** | ☐ | |
| 8.9 | Participant **rejects** a request | Nothing moves; that share permanently stays with the payer; payer notified (FR-066) | ☐ | |
| 8.10 | Leave a request untouched for 7+ days (or adjust server clock / trigger expiry job) | Treated as rejected automatically; payer notified (FR-067) | ☐ | |
| 8.11 | Payer edits or cancels a split **before anyone has accepted** | Allowed; all participants' pending responses reset and they're re-notified (FR-068, FR-069) | ☐ | |
| 8.12 | Payer tries to edit/cancel a split **after at least one participant accepted** | Blocked — split is locked (FR-068) | ☐ | |
| 8.13 | Try to edit or cancel an **already-accepted** individual share | Not possible from either side (FR-068) | ☐ | |
| 8.14 | View split history | Shows bill, participants, each one's share and status (pending/accepted/rejected/expired/cancelled) (FR-070) | ☐ | |
| 8.15 | Confirm there is **no** "who owes whom" balance screen or settle-up feature anywhere | Correct for v1 (FR-071 — Option A was chosen, no debts) | ☐ | |

---

## 9. Block User & Groups (FR-072 to FR-079)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 9.1 | Block a user by username | Succeeds | ☐ | |
| 9.2 | Blocked user tries to send you a split request or group invite | Fails with a generic message, no mention of being blocked (FR-072) | ☐ | |
| 9.3 | Unblock the user | They can send requests again | ☐ | |
| 9.4 | Create a group with a name and initial members | Succeeds, creator recorded | ☐ | |
| 9.5 | Any **non-creator member** invites a new user | Invite sent; new user must accept to join (FR-074) | ☐ | |
| 9.6 | Invited user rejects/ignores vs accepts | Accept adds them as active member; otherwise they don't join | ☐ | |
| 9.7 | A **non-creator** member tries to rename or delete the group | Blocked (FR-076) | ☐ | |
| 9.8 | The **creator** renames and deletes the group | Both succeed | ☐ | |
| 9.9 | Creator leaves the group (not deleting it) | Earliest-joined remaining member automatically becomes the new creator (FR-077) | ☐ | |
| 9.10 | Last remaining member leaves | Group auto-deletes; existing past split records are unaffected (FR-078) | ☐ | |
| 9.11 | Create a split sent to a whole group (not ad-hoc) | All current members receive it, no subset selection available (FR-063) | ☐ | |

---

## 10. Notifications (FR-080 to FR-084)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 10.1 | Trigger several notification types (split request, budget 80%, recurring skipped, goal completed, etc.) | Each appears in the list with correct type/content | ☐ | |
| 10.2 | Mark one notification as read | Unread badge count decreases by 1 | ☐ | |
| 10.3 | "Mark all as read" | Badge goes to 0, all items show read | ☐ | |
| 10.4 | Leave the app open; trigger a new notification from another session | Unread count updates within the polling interval (~30s), no page reload needed (FR-082) | ☐ | |

---

## 11. Dashboard & Export (FR-090 to FR-094)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 11.1 | Dashboard shows current balance, income vs expense this month, category breakdown, budget progress (overall + category), recent transactions, goals progress, 6-month trend | All present and numerically correct against manually totaled data | ☐ | |
| 11.2 | Export transactions as CSV with a date range filter | Only matching rows included, amounts correct | ☐ | |
| 11.3 | Export as Excel (.xlsx) | Opens correctly, correct data | ☐ | |
| 11.4 | Export as PDF | Shows a transactions table **plus** a summary (total income, total expense, net, count); **no charts** in the PDF (FR-093) | ☐ | |
| 11.5 | As User A, confirm export never includes User B's transactions | FR-094 | ☐ | |

---

## 12. Appearance (FR-100 to FR-102)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 12.1 | Switch OS/browser to dark mode with no in-app override set | App follows system theme automatically | ☐ | |
| 12.2 | Manually override theme in-app | Overrides system preference and persists across reload/logout-login | ☐ | |
| 12.3 | Resize browser to a phone width (or use device emulation) | Layout remains usable, no horizontal scroll/broken elements (FR-102) | ☐ | |
| 12.4 | Confirm no non-English text appears anywhere in the UI | FR-101 | ☐ | |

---

## 13. Security spot-checks (NFR-001 to NFR-010)

| # | Check | Expected | Result | Notes |
|---|---|---|---|---|
| 13.1 | Inspect network requests — is the JWT access token ever logged to console or visible in a URL? | Should never appear in URLs; ideally not in persistent storage either | ☐ | |
| 13.2 | Try calling the daily job endpoint (`/internal/jobs/daily`) without the `CRON_SECRET` header | Rejected (NFR-009) | ☐ | |
| 13.3 | Check API responses never include `password_hash` or refresh-token values | NFR-006 | ☐ | |
| 13.4 | Trigger two simultaneous split-accepts on the same split from two browser tabs quickly | No double-debit, no corrupted balance (NFR-010 — race condition check) | ☐ | |
| 13.5 | Repeat test 1.15 (cross-user data isolation) on at least 3 different endpoints (transactions, goals, groups) | All blocked consistently | ☐ | |

---

## How to report a failure back to the agent

For every ❌, give: the test number, what you did, what you expected (quote the FR/NFR), and what actually happened (screenshot if visual). This lets the agent fix the exact requirement instead of guessing, and lets you re-run just that section afterward.
