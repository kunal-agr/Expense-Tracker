# Software Requirements Specification: Expense Tracker

| Field | Value |
|---|---|
| Document version | 1.0.0 |
| Target release | v1 |
| Status | Draft for implementation |
| Implementer | Antigravity (AI agent) |
| Date | 2026-11-18 |

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-11-18 | Initial SRS for v1 |

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for a multi-user personal expense tracker with bill splitting. It is the single source of truth for implementation. Every requirement has an ID and a target version. **Only requirements tagged `[v1]` are to be built now.** Items tagged `[v2]`, `[v3]` or `[Later]` must not be built, but the v1 design must leave room for them (Section 14).

### 1.2 Scope (v1)
A web application where users register, track income and expenses in a single wallet, set budgets, save toward goals, create recurring monthly transactions, split bills with other users (individually or in groups), receive in-app notifications, and export their data.

### 1.3 Out of scope for v1
Email of any kind (welcome, verification, password reset), Google OAuth, UPI or any payment integration, receipt OCR, bank/CSV import, 2FA, admin role, multiple wallets, multi-currency, multi-language, debt tracking, debt simplification, mobile app, mandatory automated testing.

### 1.4 Definitions
- **Wallet:** the single balance container of a user.
- **Payer:** the user who created a split and paid the bill.
- **Participant:** a user who owes a share in a split (the payer is also a participant).
- **Share:** the amount one participant owes.
- **IST:** Asia/Kolkata (UTC+05:30).

### 1.5 Requirement priority
All `[v1]` requirements are mandatory unless marked *(Should)*.

---

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Backend language | Python 3.13.7 |
| Backend framework | FastAPI |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Validation | Pydantic v2 |
| Database | PostgreSQL (local install for dev; Supabase in production, used only as PostgreSQL, not its auth) |
| Password hashing | Argon2 (argon2-cffi) |
| Auth | JWT access token + refresh token, per-device session rows |
| Rate limiting | slowapi (in-memory in v1) |
| Excel export | openpyxl |
| PDF export | reportlab (or WeasyPrint) |
| Frontend | React + Vite + TypeScript, Node 24.11.0 |
| Styling | Tailwind CSS with a custom design system (Section 12) |
| Data fetching | TanStack Query |
| Routing | React Router |
| Charts | Recharts |
| Forms/validation | React Hook Form + Zod |
| Local dev | Native installs, **no Docker** |

Tech-stack changes require a changelog entry in this document.

### 2.1 Database access rule (binding, non-negotiable)
**NFR-000 [v1]** All database access must go through an **ORM** (SQLAlchemy 2.x in this project). Raw SQL strings are not permitted anywhere in application code, including inside migrations' data-fixing scripts (Alembic's auto-generated DDL is the only exception). This is a standing rule for this project **and all future projects by this product owner**: whatever the backend language or framework, data access goes through an ORM (e.g. SQLAlchemy/SQLModel for Python, Prisma for Node/Next.js), never hand-written queries glued into application code. Reasons: SQL-injection protection by default, type safety, consistent migration tooling, and portability if the database engine ever changes.

---

## 3. Users and Roles

- **User:** the only role. All users are equal. There is **no admin** in v1.
- **Group creator:** a per-group role, not an app role (Section 7.3).

---

## 4. Authentication and Account

### 4.1 Functional requirements

- **FR-001 [v1]** Register with email, username, password. Email is unique (case-insensitive).
- **FR-002 [v1]** Username rules: 3 to 20 characters, lowercase letters, digits and underscore only; stored lowercase; input is case-insensitive; unique.
- **FR-003 [v1]** Password minimum length is 6 characters. Stored only as an Argon2 hash. Never logged or returned.
- **FR-004 [v1]** Login with **either email or username** plus password.
- **FR-005 [v1]** Login returns a short-lived JWT access token (15 minutes) and a refresh token (7 days). Each login creates one **session row** in the database (device/user-agent, IP, created_at, last_used_at, revoked_at). Multiple simultaneous sessions (devices) are allowed.
- **FR-006 [v1]** Refresh endpoint exchanges a valid, non-revoked refresh token for a new access token. Refresh tokens are rotated on each use; reuse of an old token revokes that session. Refresh tokens are stored hashed.
- **FR-007 [v1]** Logout revokes the current session. "Log out of all devices" revokes all of the user's sessions.
- **FR-008 [v1]** User can change username at any time. The old username is freed immediately. Uniqueness rules still apply.
- **FR-009 [v1]** Setup after first registration: user must enter an **opening balance (minimum ₹100, whole rupees)** before reaching the app. The wallet is created at this step.
- **FR-010 [v1]** Opening balance can be edited later (minimum ₹100). The edit shifts only the current balance by the difference; existing transactions are untouched. The edit is blocked if it would make the current balance negative.
- **FR-011 [v1]** Account deletion: requires password confirmation. Blocked never by balances (no debts exist in v1). On delete:
  1. All pending splits created by or addressed to the user are cancelled and the other parties are notified.
  2. Personal data is deleted (profile, wallet, transactions, categories, budgets, goals, recurring rules, notifications, sessions, blocks).
  3. Accepted split history owned by other users is kept; the deleted user is shown as **"Deleted user"**.
  4. Group memberships are removed (creator succession in FR-052 applies).
  5. The username is freed.
- **FR-012 [v1]** Registration, login and all auth endpoints are rate limited (Section 11).
- **FR-013 [v2]** Welcome email, email verification, password reset (requires SMTP).
- **FR-014 [v2]** Google OAuth login (first login asks user to choose a username; no auto-linking by email).

### 4.2 Known accepted risks (v1)
- No password reset: an email+password user who forgets the password cannot recover the account.
- Emails are not verified: anyone can register with any email address.

Both are accepted by the product owner and are resolved in v2.

---

## 5. Wallet and Transactions

### 5.1 Money rules
- **FR-020 [v1]** All amounts are **whole rupees** stored as integers (no decimals, no floats). Currency is INR only.
- **FR-021 [v1]** Display uses the Indian digit grouping, e.g. `₹1,00,000` (`Intl.NumberFormat('en-IN')`).
- **FR-022 [v1]** Current balance = opening balance + total income - total expense - net goal contributions (Section 6.3). The balance must **never be negative**. This is enforced in application logic **and** by a database CHECK constraint, and all money-moving operations run inside database transactions.

### 5.2 Transactions
- **FR-023 [v1]** Create, view, edit, delete transactions. Fields: type (income/expense), amount (≥ 1), date, category, optional subcategory, payment method (UPI / Card / Cash; applies to both income and expense), optional note.
- **FR-024 [v1]** Date may be **today or any past date**. Future dates are rejected.
- **FR-025 [v1]** An expense larger than the current balance is **blocked** with a clear message.
- **FR-026 [v1]** Editing or deleting a transaction (or the opening balance) that would make the current balance negative is **blocked**. Only the **current** balance is checked, not historical balance on a backdated date.
- **FR-027 [v1]** Transactions created by split acceptance (Section 7) are **read-only**: they cannot be edited or deleted by the user.
- **FR-028 [v1]** List with search (note text), filters (date range, category, type, payment method), sort (date, amount), and pagination.

### 5.3 Categories
- **FR-030 [v1]** Each user gets a seeded copy of the starter categories (Appendix A). Users can add custom categories and subcategories (one level of nesting).
- **FR-031 [v1]** Rename is always allowed. Delete is **blocked if any transaction uses the category/subcategory**; otherwise allowed. Deleting a category also deletes its empty subcategories and its category budget.
- **FR-032 [v1]** The categories **"Shared"** (expense) and **"Other"** (expense and income) are protected: they cannot be deleted. "Shared" cannot be renamed.

---

## 6. Budgets, Goals, Recurring

### 6.1 Budgets
- **FR-040 [v1]** Overall monthly budget: a single amount, set once, **repeats every month automatically** until the user changes it. Changing it applies from the current month onward.
- **FR-041 [v1]** Per-category monthly budgets: each repeats every month. Spending in a subcategory counts toward its parent category.
- **FR-042 [v1]** The overall budget must be set before any category budget. The **sum of category budgets cannot exceed the overall base budget**. Lowering the overall budget below the category total is blocked.
- **FR-043 [v1]** **Carry-forward applies to the overall budget only.** Effective overall budget for month M = base budget + unused amount of month M-1 (unused = max(0, effective(M-1) - spent(M-1))). Category budgets do not carry forward.
- **FR-044 [v1]** "Spent" counts expense transactions in the month (including "Shared" expenses). Savings goal contributions are **not** counted as spending.
- **FR-045 [v1]** In-app notifications at **80% and 100%** of the overall budget and of each category budget. Each threshold fires **at most once per budget per month**.
- **FR-046 [v1]** Exceeding a budget **never blocks** an expense. A warning is shown at entry time and a notification is sent. The deficit is **not** deducted from next month's budget.
- **FR-047 [v1]** Month boundaries are by **IST** (1st, 00:00 IST). Timestamps are stored in UTC.

### 6.2 Recurring transactions
- **FR-048 [v1]** User can create recurring **income or expense** rules. Frequency: **monthly only** (the field must support other values later, Section 14). Fields: type, amount, category, payment method, note, day of month, start date, optional end date.
- **FR-049 [v1]** Rules are created **automatically** on schedule; no confirmation. If the chosen day does not exist in a month (29/30/31), the **last day of that month** is used.
- **FR-050 [v1]** User can edit, pause/resume, delete a rule, and set an end date. Edits affect future occurrences only.
- **FR-051 [v1]** If an **expense** occurrence cannot be applied because the balance is too low, it is **skipped** for that month and the user gets an in-app notification (e.g. "EMI not added: insufficient balance"). It is not retried automatically; the user can add it manually. Income occurrences always apply.
- **FR-052a [v1]** Each successful auto-add sends an in-app notification.
- **FR-052b [v1]** Scheduling: an external cron service calls a secured endpoint daily (Section 13). As a backup, on user login the system **catches up** any missed occurrences in chronological order. Occurrence processing is **idempotent** (a given rule/date is applied at most once).

### 6.3 Savings goals
- **FR-053 [v1]** Create goal: name, target amount, optional deadline. Edit and delete.
- **FR-054 [v1]** Contribute to a goal: money **moves from the wallet** to the goal (subject to the balance rule). User can **withdraw** from a goal back to the wallet. Contributions/withdrawals are recorded in a goal history, not as income/expense.
- **FR-055 [v1]** When saved amount reaches the target, the goal is marked **completed** and a notification is sent. Money stays in the goal until the user withdraws it. Deleting a goal returns its saved amount to the wallet.

---

## 7. Bill Splitting

### 7.1 Core rules
- **FR-060 [v1]** A split is created by the **payer** for a bill amount. The payer is automatically a participant. The bill is recorded as an expense of the **full amount** for the payer at creation (requires sufficient balance).
- **FR-061 [v1]** Split types: **exact amounts**, **percentages**, **shares**. Exact amounts must sum to the bill; percentages must sum to 100.
- **FR-062 [v1]** Because amounts are whole rupees, a split may leave a remainder of a few rupees. **At creation the payer chooses who bears the remainder** (the payer or any one participant) before the split can be sent.
- **FR-063 [v1]** **Ad-hoc split:** payer picks other users by **username**. **Group split:** the split goes to **all** current group members (no subset).
- **FR-064 [v1]** Each other participant receives a split request as an in-app notification and can **accept** or **reject**.
- **FR-065 [v1] On accept** (atomic, one database transaction):
  1. The participant's balance is checked. If balance < share, accept is **blocked**, the request stays pending, and the participant gets a notification ("insufficient balance").
  2. Participant's wallet is debited by their share; a read-only **"Shared"** expense of that share is created for them.
  3. Payer's wallet is credited by the same share; the payer's original expense is reduced by that share.
  4. Both parties are notified.
  
  Example: Alex pays ₹900, 3-way equal. Alex's expense starts at ₹900. Alice accepts: Alice -₹300, Alex +₹300, Alex's expense becomes ₹600. Jack accepts: expense becomes ₹300.
- **FR-066 [v1]** **On reject or expiry:** nothing moves; that share stays with the payer; the payer gets an in-app notification.
- **FR-067 [v1]** Requests **expire after 7 days** and are treated as rejected. Expiry is applied by the scheduled job and also lazily when a request is accessed.
- **FR-068 [v1]** The payer can **edit or cancel** a split only while **no participant has accepted**. Once any participant accepts, the split is **locked**; remaining pending shares stay actionable until accept/reject/expiry. A participant's accepted share is final and cannot be edited or deleted by either side.
- **FR-069 [v1]** A cancelled/edited split notifies participants. Editing resets all responses.
- **FR-070 [v1]** Split history view: for each split, the bill, participants, share, status (pending / accepted / rejected / expired / cancelled).
- **FR-071 [v1]** No "owes" balances, no settle-up, no debt simplification in v1 (money moves only on accept).

### 7.2 Block user
- **FR-072 [v1]** A user can block another user by username and unblock later. A blocked user **cannot send that user split requests or group invites**. The attempt fails with a generic message that does not reveal the block. Blocking does not affect already-accepted splits or existing shared groups (the blocker may leave the group).

### 7.3 Groups
- **FR-073 [v1]** Any user can create a permanent group (name, members). The creator is the **group creator**.
- **FR-074 [v1]** **Any member can invite** another user by username. The invitee must **accept** the invite to join (in-app notification). Blocked users cannot be invited by the blocker's blockees (FR-072).
- **FR-075 [v1]** Members can **leave at any time**. Joining and leaving is up to each member.
- **FR-076 [v1]** Only the **creator** can rename or delete the group.
- **FR-077 [v1]** If the creator leaves (or deletes their account), the **earliest-joined remaining member becomes the creator**.
- **FR-078 [v1]** If the last member leaves, the group is deleted automatically. Deleting a group does not alter past split records.
- **FR-079 [v1]** Pending split requests for a group whose recipient leaves the group remain valid until expiry or action.

---

## 8. Notifications (in-app only)

- **FR-080 [v1]** Notification list with read/unread state, "mark all as read", and an unread badge.
- **FR-081 [v1]** Notifications older than **90 days** are deleted automatically.
- **FR-082 [v1]** v1 delivery: the frontend polls an unread-count endpoint (e.g. every 30 s) and fetches the list on open. Real-time push is not required.
- **FR-083 [v1]** Types: split request received/accepted/rejected/expired/cancelled/edited; accept blocked (insufficient balance); group invite; budget 80%/100% (overall and per category); recurring added/skipped; goal completed.
- **FR-084 [v1]** Notifications go through a **channel abstraction** (in-app only now) so that email can be added in v2 without redesign.

---

## 9. Dashboard and Export

### 9.1 Dashboard (in-app charts only)
- **FR-090 [v1]** Show: current balance; this month's income vs expense; category-wise spending (donut or bar); overall and per-category budget progress; recent transactions; savings goals progress; income vs expense trend (last 6 months).

### 9.2 Export
- **FR-091 [v1]** Export **transactions only**, formats **CSV, Excel (.xlsx), PDF**.
- **FR-092 [v1]** Filters before export: date range, category, type.
- **FR-093 [v1]** PDF contains a transactions **table plus a summary** (total income, total expense, net, count). **No charts** in PDF.
- **FR-094 [v1]** Export contains only the requesting user's data. Amounts exported as plain numbers in CSV/Excel.

---

## 10. Appearance

- **FR-100 [v1]** Light and dark themes. Default follows **system preference**; the user can override; the choice persists.
- **FR-101 [v1]** UI language is English only.
- **FR-102 [v1]** Layout is fully responsive (phone widths supported) so the same backend and UI patterns carry to the future mobile app.

---

## 11. Non-Functional Requirements

### 11.1 Security
- **NFR-001 [v1]** HTTPS in production. CORS allows only the configured frontend origin(s).
- **NFR-002 [v1]** **Data isolation:** every query is scoped to the authenticated user (or to explicit split/group membership). A user must never read or modify another user's data. This is enforced centrally (shared dependency/query helper), not ad hoc per endpoint.
- **NFR-003 [v1]** All input validated with Pydantic; database access only through the ORM / parameterized queries.
- **NFR-004 [v1]** **Rate limiting** (bot protection): login and register **5 requests/minute per IP**; other endpoints a general limit (default 100 requests/minute per user/IP, configurable via `.env`). Excess returns HTTP 429.
- **NFR-005 [v1]** **Secrets** only in `.env`, never in git, never hardcoded. A `.env.example` with placeholder values is committed.
- **NFR-006 [v1]** Passwords hashed with Argon2. Refresh tokens stored hashed. Sensitive fields never appear in logs or API responses.
- **NFR-007 [v1]** Generic error messages on login failure (do not reveal whether email/username exists).
- **NFR-008 [v1]** Security headers set on responses; dependency versions pinned.
- **NFR-009 [v1]** The scheduled-job endpoint requires a secret header (`CRON_SECRET`) and is not usable by normal users.
- **NFR-010 [v1]** Money-moving operations (split accept, goal contribution, recurring apply) use database transactions with row locking to prevent double-spend and race conditions.

### 11.2 Performance and scalability
- **NFR-020 [v1]** Reasonable defaults: indexed foreign keys and common filter columns (user_id, date, category_id), paginated lists. Formal performance targets, caching, Redis and load testing are **[v2]**.

### 11.3 Usability
- **NFR-030 [v1]** Clear empty states, loading and error states, and confirmation for destructive actions.

### 11.4 Maintainability
- **NFR-040 [v1]** API versioned at `/api/v1`. OpenAPI docs auto-generated by FastAPI. Alembic migration for every schema change. Code is typed (Python type hints, TypeScript).

---

## 12. UI/UX Design Brief

**Reference:** Linear (layout and feel only). **Goal:** it must not look like generic AI-generated UI, so no default indigo/purple, no stock gradient hero, no card-on-card clutter.

### 12.1 Principles
- Dark-first feel, minimal, dense but readable, tight consistent spacing (4px grid).
- Thin 1px borders, almost no shadows, no gradients.
- Left sidebar navigation, a slim top bar, content in a calm single column or two-pane layout.
- Quiet motion only (100-150 ms fades/slides). Skeleton loaders instead of spinners.
- Keyboard-friendly (focus rings visible, logical tab order). A command palette / shortcuts are optional *(Should)*.
- Amounts always in **tabular, monospace numerals**, right aligned, Indian grouping; income and expense indicated by color **and** sign.

### 12.2 Design direction: "Saffron" (primary)
- **Font:** Geist Sans (UI) + Geist Mono (numbers). Alternatives if needed: Manrope + JetBrains Mono (teal accent option), General Sans or Plus Jakarta Sans + IBM Plex Mono (coral accent option).
- **Tokens** (define as CSS variables; Tailwind reads them):

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#FAFAF8` | `#0E0E10` |
| `--surface` | `#FFFFFF` | `#151518` |
| `--surface-2` | `#F2F1ED` | `#1C1C20` |
| `--border` | `#E4E2DC` | `#26262B` |
| `--text` | `#1A1A1A` | `#ECECEE` |
| `--text-muted` | `#6B6A66` | `#8B8B93` |
| `--accent` | `#D98A1F` | `#F2A93B` |
| `--accent-text` | `#FFFFFF` | `#1A1204` |
| `--income` | `#2E8B57` | `#4CC38A` |
| `--expense` | `#C8453A` | `#F2766B` |
| `--warning` | `#B7791F` | `#E5B454` |

- Radius: 6px for controls, 8px for panels. No pill-everything.
- Charts: use accent + muted neutrals, with income/expense tokens where meaning is semantic; no rainbow palettes.
- The theme must meet WCAG AA contrast for text.

### 12.3 Screens
Register / Login, Setup (opening balance), Dashboard, Transactions, Categories, Budgets, Goals, Recurring, Splits (requests, history, create), Groups, Notifications, Settings (profile, username, theme, blocked users, sessions, export, delete account).

---

## 13. Architecture, Repository and Deployment

### 13.1 Architecture
Single-page React app calls a stateless FastAPI REST API (`/api/v1`) backed by PostgreSQL. The API is client-agnostic so a mobile app can use it unchanged in v3.

### 13.2 Monorepo layout
```
expense-tracker/
├── backend/        FastAPI app, Alembic, requirements.txt, .env.example
├── frontend/       React + Vite app, .env.example
├── docs/           SRS.md and other docs
├── CHANGELOG.md
├── README.md
└── .gitignore
```

### 13.3 .gitignore (minimum)
`.env`, `.env.*` (except `.env.example`), `__pycache__/`, `*.pyc`, `venv/`, `.venv/`, `node_modules/`, `dist/`, `build/`, `*.db`, `*.sqlite`, `*.log`, `.idea/`, `.vscode/`, `.DS_Store`, `.pytest_cache/`, `coverage/`, exported files.

### 13.4 Environment variables (backend, example names)
`DATABASE_URL`, `JWT_SECRET`, `JWT_ACCESS_MINUTES=15`, `JWT_REFRESH_DAYS=7`, `FRONTEND_ORIGIN`, `CRON_SECRET`, `RATE_LIMIT_DEFAULT`. Frontend: `VITE_API_URL`.

### 13.5 Local development
Local PostgreSQL, Python 3.13.7 venv, Node 24.11.0. Run backend with uvicorn and frontend with Vite. No Docker in v1.

### 13.6 Production deployment (after local build is complete)
- **Frontend: Vercel.** Root Directory `frontend`, build `npm run build`, output `dist`, `vercel.json` rewrite to `index.html` for client routing, `VITE_API_URL` set in dashboard.
- **Backend: Render** Web Service. Root Directory `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Python version pinned, Alembic migrations run on deploy, build filter on `backend/**`.
- **Database: Supabase** PostgreSQL via the **connection pooler** string in `DATABASE_URL`. Used only as a database.
- **Scheduler:** an external cron (e.g. cron-job.org) calls the secured job endpoint daily. It processes recurring rules, split expiry, notification cleanup. This also keeps a sleeping free-tier backend awake once a day.
- **Pre-deploy checklist (to be re-verified at deploy time):** current free-tier limits and sleep behavior of Render and Supabase; CORS between Vercel and Render origins; refresh-token cookie strategy across domains (Section 13.7); production env vars; Google OAuth redirect URLs are v2.

### 13.7 Refresh-token transport (decision to confirm at deploy)
Web: refresh token in an **httpOnly, Secure cookie** (`SameSite=None` in production because frontend and backend are on different domains, with CORS credentials enabled). Access token held in memory only. Because third-party cookie handling varies by browser, this must be validated when deploying; fallback is a custom domain that shares a parent domain between frontend and backend. Future mobile clients receive the refresh token in the response body and store it in secure storage.

### 13.8 Git workflow
- Branches: `main` (stable) plus feature branches (`feat/...`, `fix/...`, `docs/...`), merged via pull requests.
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Documentation is committed separately and properly, e.g. `docs: add SRS v1.0.0`.
- Releases tagged with semantic versions (`v1.0.0`, `v2.0.0`), each with a `CHANGELOG.md` entry.
- Never commit secrets or ignored files.

---

## 14. Future-proofing in the v1 Design (design now, build later)

| Future item | What v1 must do now |
|---|---|
| v2 Google OAuth | Users table: `password_hash` nullable; `auth_provider` and `provider_user_id` columns |
| v2 Email | Notification channel abstraction (FR-084); `email_verified` column (default false) |
| v2 Password reset | Token table can be added without changing users |
| v3 Mobile (Flutter or React Native, undecided) | API-first, `/api/v1`, token auth that works for non-browser clients, responsive UI |
| Later: other recurring frequencies | `frequency` column on recurring rules (only `monthly` accepted) |
| Later: multiple wallets | Separate `wallets` table linked to user; v1 enforces exactly one |
| Later: debts / settle-up | Not modeled in v1 |

---

## 15. Data Model (logical)

- **users**: id, email (unique, ci), username (unique, lowercase), password_hash (nullable), auth_provider, provider_user_id, email_verified, created_at
- **sessions**: id, user_id, refresh_token_hash, user_agent, ip, created_at, last_used_at, expires_at, revoked_at
- **wallets**: id, user_id (unique in v1), opening_balance, current_balance (CHECK ≥ 0)
- **categories**: id, user_id, parent_id (nullable), name, type (income/expense), is_protected
- **transactions**: id, user_id, wallet_id, type, amount, date, category_id, subcategory_id, payment_method, note, source (manual/recurring/split), split_id (nullable), read_only, created_at
- **budgets**: id, user_id, scope (overall/category), category_id (nullable), amount, effective_from
- **budget_alerts**: id, budget_id, month, threshold (80/100) (unique per budget, month, threshold)
- **goals**: id, user_id, name, target_amount, saved_amount, deadline, status
- **goal_entries**: id, goal_id, amount (+/-), created_at
- **recurring_rules**: id, user_id, type, amount, category_id, payment_method, note, frequency, day_of_month, start_date, end_date, is_paused
- **recurring_runs**: id, rule_id, run_date, status (applied/skipped), unique (rule_id, run_date)
- **splits**: id, payer_id, group_id (nullable), total_amount, split_type, note, status, remainder_bearer_id, created_at, expires_at, locked_at
- **split_participants**: id, split_id, user_id (nullable after deletion), share_amount, status (pending/accepted/rejected/expired), responded_at
- **groups**: id, name, creator_id, created_at
- **group_members**: id, group_id, user_id, joined_at, status (invited/active)
- **blocks**: id, blocker_id, blocked_id
- **notifications**: id, user_id, type, payload (JSON), is_read, created_at

---

## 16. API Outline (`/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/sessions` |
| Account | `GET/PATCH /me`, `PATCH /me/username`, `PUT /me/opening-balance`, `DELETE /me` |
| Wallet | `GET /wallet` |
| Transactions | `GET/POST /transactions`, `GET/PATCH/DELETE /transactions/{id}` |
| Categories | `GET/POST /categories`, `PATCH/DELETE /categories/{id}` |
| Budgets | `GET/PUT /budgets/overall`, `GET/PUT/DELETE /budgets/categories/{id}`, `GET /budgets/status?month=` |
| Goals | `GET/POST /goals`, `PATCH/DELETE /goals/{id}`, `POST /goals/{id}/contribute`, `POST /goals/{id}/withdraw` |
| Recurring | `GET/POST /recurring`, `PATCH/DELETE /recurring/{id}`, `POST /recurring/{id}/pause`, `POST /recurring/{id}/resume` |
| Splits | `POST /splits`, `GET /splits`, `GET/PATCH/DELETE /splits/{id}`, `POST /splits/{id}/accept`, `POST /splits/{id}/reject` |
| Groups | `GET/POST /groups`, `PATCH/DELETE /groups/{id}`, `POST /groups/{id}/invite`, `POST /groups/{id}/accept`, `POST /groups/{id}/leave` |
| Blocks | `GET/POST /blocks`, `DELETE /blocks/{username}` |
| Notifications | `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Dashboard | `GET /dashboard?month=` |
| Export | `GET /export/transactions?format=csv|xlsx|pdf&from=&to=&category=&type=` |
| Jobs | `POST /internal/jobs/daily` (requires `CRON_SECRET`) |

Standard error format with machine-readable code and human message; HTTP 401/403/404/409/422/429 used appropriately.

---

## 17. Decisions made by the author on the owner's behalf (please review)

These were left to the author by the product owner. They are binding for v1 unless changed (and logged in the changelog).

1. Group creator succession = earliest-joined remaining member (FR-077). Any member can invite; invitee accepts (FR-074).
2. Blocked user sees a generic failure, not the block (FR-072). Block list can be managed and unblocked.
3. Split locks after the first participant accepts (FR-068).
4. Payment method applies to both income and expense (FR-023).
5. Backdated edits check only the current balance (FR-026).
6. Opening balance edit shifts only current balance; blocked if it would go negative (FR-010).
7. Savings goals: withdraw allowed; completion = marked complete, funds stay until withdrawn; deleting returns funds (FR-054, FR-055).
8. Savings contributions are not counted as spending for budgets (FR-044).
9. Carry-forward chains month to month and is overall-only (FR-043).
10. Budget alerts fire once per threshold per month (FR-045).
11. Category budgets: overall must exist first; sum cannot exceed overall; lowering overall below the sum is blocked (FR-042).
12. Recurring: skipped expenses are not retried; income always applies; catch-up on login (FR-051, FR-052b).
13. Account delete cancels pending splits and removes memberships (FR-011).
14. Categories are seeded per user; "Shared" and "Other" are protected (FR-032).
15. Notifications via polling (30 s) in v1 (FR-082).
16. Rate-limit numbers: auth 5/min/IP, general 100/min (NFR-004).
17. Session = JWT access (15 min) + refresh (7 days, rotating) with a DB session row per device (FR-005 to FR-007).
18. Refresh token as httpOnly cookie for web, to be validated at deploy (Section 13.7).
19. Design direction "Saffron" with Geist fonts and the token table in Section 12.
20. Password minimum is 6 as requested. **Recommendation:** raise to 8 before public launch.
21. Dashboard widgets list (FR-090).
22. Export filter set: date range, category, type (FR-092).

---

## 18. Testing

Automated testing is **not mandatory in v1**. If the product owner decides to start testing, the intended approach is:

- **Backend:** pytest + httpx/TestClient against a separate test database, with coverage reporting.
- **Frontend:** Vitest + React Testing Library.
- **End-to-end:** Playwright.
- **Priority areas if testing starts:** split accept/reject/expiry, wallet balance rules, budget carry-forward and alerts, recurring day clamping and idempotency, data isolation (user A cannot access user B).
- **Later (v2):** CI via GitHub Actions, load tests (Locust or k6), security scans (bandit, pip-audit, npm audit).

---

## 19. Roadmap

| Version | Contents |
|---|---|
| **v1** | Everything tagged `[v1]` in this document, then deployment (Vercel + Render + Supabase) |
| **v2** | SMTP (welcome email, verification, password reset), Google OAuth, testing suite and CI, performance/security hardening (Redis rate limiting, caching, load tests) |
| **v3** | Mobile app (Flutter or React Native, to be decided) on the same API |
| **Later** | Debts and settle-up, debt simplification, 2FA, receipt OCR, bank/CSV import, UPI, admin role, extra recurring frequencies, multi-wallet, multi-language, real-time notifications |

---

## Appendix A: Starter Categories

**Expense**
- Food & Dining: Groceries, Restaurants, Snacks & Cafe
- Transport: Fuel, Public Transport, Cab/Auto
- Housing: Rent, Maintenance, Electricity/Water/Gas
- Bills & Recharge: Mobile, Internet, DTH
- Shopping: Clothing, Electronics, Household
- Health: Medical, Pharmacy, Fitness
- Entertainment: Movies, Subscriptions, Games
- Education
- Travel
- Personal Care
- EMI/Loans
- Insurance
- Gifts & Donations
- **Shared** (protected, used by accepted splits)
- **Other** (protected)

**Income**
Salary, Freelance, Business, Investments, Gift, Refund, **Other** (protected)

## Appendix B: Suggested documentation commits

```
docs: add SRS v1.0.0
docs: add README with local setup and project structure
chore: add .gitignore and .env.example
docs: add CHANGELOG.md
```
