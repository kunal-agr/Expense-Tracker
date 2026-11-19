# Kickoff Prompt for Antigravity

You are building a **full-stack Expense Tracker web application**. The complete requirements are in the attached `SRS.md` (Software Requirements Specification). Read it fully before writing any code. This prompt tells you *how* to work; the SRS tells you *what* to build. Follow both together.

## 1. Scope discipline (read this twice)

- Build **only** requirements tagged `[v1]` in the SRS. Every FR/NFR has a version tag.
- Requirements tagged `[v2]`, `[v3]`, or `[Later]` must **not** be implemented, not even partially, not even as empty stubs beyond what Section 14 ("Future-proofing") explicitly asks for (e.g. a nullable column). Do not add OAuth, email sending, payment integration, mobile code, or admin features.
- Section 17 of the SRS ("Decisions made by the author on the owner's behalf") lists product decisions that are already final. Treat them as settled — do not re-ask the product owner about them, and do not silently change them.
- If you hit a genuine gap the SRS does not answer, do not silently invent product behavior. Either:
  (a) pick the most conservative, reversible option and clearly log it in `docs/ASSUMPTIONS.md` with the reason, or
  (b) stop and ask the product owner, if the decision is costly to reverse (e.g. changes the data model or money logic).

## 2. Hard technical rules (non-negotiable)

- **ORM only** (SQLAlchemy 2.x + Alembic, per SRS NFR-000). No raw SQL strings anywhere in application code. Alembic's own auto-generated DDL is the only exception.
- **Whole-rupee integers only** for all money fields — no floats, no decimals, anywhere in the stack (DB, API, frontend state).
- Every money-moving operation (split accept, goal contribution/withdrawal, recurring apply, opening-balance edit) must run inside a **database transaction with row locking**, and must re-check the balance invariant (`current_balance >= 0`) before committing.
- **Data isolation is enforced centrally**, not per-endpoint ad hoc — build one shared dependency/query helper that scopes every query to the authenticated user (or explicit split/group membership), and route all endpoints through it.
- Secrets only in `.env`; commit only `.env.example` with placeholder values. Set up `.gitignore` (Section 13.3 of the SRS) **before** the first commit that touches real code.
- No Docker in v1 (Section 13.5) — native local dev only.

## 3. Build order

Work in this order. Do not jump ahead to a later phase before the current one is working end-to-end (migrations run, basic manual test passes).

1. **Repo scaffold:** monorepo layout from SRS Section 13.2, `.gitignore`, `.env.example` (backend + frontend), `README.md` with local setup steps, empty `CHANGELOG.md`.
2. **Backend foundation:** FastAPI app skeleton, SQLAlchemy models for the full data model (SRS Section 15), first Alembic migration, health-check endpoint.
3. **Auth:** register, login (email or username), JWT access + refresh with per-device session rows, logout / logout-all, rate limiting on auth endpoints (FR-001 to FR-012, NFR-004).
4. **Wallet, opening balance setup, transactions, categories** (Sections 5, seeded starter categories from Appendix A).
5. **Budgets (overall + per-category with carry-forward), savings goals, recurring transactions** (Section 6), including the daily job endpoint and login catch-up logic.
6. **Bill splitting, block-user, groups** (Section 7) — this is the highest-risk module (money correctness); be extra careful with FR-060 to FR-079.
7. **Notifications** (Section 8).
8. **Dashboard and export (CSV/Excel/PDF)** (Section 9).
9. **Frontend:** scaffold with the design tokens and principles from Section 12 first (theme, layout shell, typography), then build screens in the same order as the backend phases above, wiring to the real API as each phase becomes available.
10. **Final pass:** verify every `[v1]` requirement against the running app, fix gaps, then prepare for deployment per Section 13.6 (do not deploy until the product owner says to proceed — flag when you're ready).

## 4. Checkpoints — stop and report

After each numbered phase in Section 3, pause and give the product owner a short status: what was built, which FR/NFR IDs are now satisfied, any assumptions logged, and what's next. Do **not** silently build the entire app in one pass and present it all at the end — early course correction is cheaper than late.

## 5. Git discipline (maintain the repo *as you build*, not at the end)

- **Step 0, before any code:** `git init`, create `.gitignore` (SRS Section 13.3), commit it, then commit `docs/SRS.md` and `docs/ANTIGRAVITY_PROMPT.md` (`docs: add SRS v1.0.0`, `docs: add kickoff prompt`). The repo must exist and have these commits before a single line of app code is written.
- **One commit per logical change, not per phase.** A phase from Section 3 (e.g. "Auth") should produce *several* commits as you go — e.g. `feat: add user and session models`, `feat: add register and login endpoints`, `feat: add JWT refresh rotation`, `fix: handle duplicate username on register` — not one giant commit dumped at the end of the phase.
- **Commit after every working slice**, meaning: it runs, migrations apply cleanly, and the thing you just added does what it says. Do not batch up hours of uncommitted work.
- Use **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`, `perf:`. Scope prefix is encouraged where useful, e.g. `feat(splits): add percentage-based split creation`.
- **Every new Alembic migration is its own commit**, separate from the feature code that needed it, e.g. `chore(db): add migration for recurring_rules table` then `feat: add recurring rule CRUD endpoints`.
- **Update `CHANGELOG.md` at the end of each phase** (not every commit) with a short bullet list of what shipped, under an `[Unreleased]` heading until v1 is tagged.
- **Never commit a broken state** (failing migration, app that won't start) to the primary branch. If you must pause mid-feature, commit to a short-lived branch instead.
- **Never commit secrets** or anything in `.gitignore`; if something slips in, remove it from history before continuing, don't just delete the file in a later commit.
- At the end of each checkpoint in Section 4, report the **commit range** (or `git log --oneline` for that phase) alongside the status update, so the product owner can review the actual diffs, not just a summary.
- When v1 is fully done and self-checked (Section 7), tag it `v1.0.0` and add the corresponding `CHANGELOG.md` entry.

## 6. Testing

Automated tests are **not mandatory** for v1 (SRS Section 18). If you do add tests, prioritize: split accept/reject/expiry math, wallet balance invariants, budget carry-forward, recurring day-clamping and idempotency, and data isolation. Do not let testing setup block feature delivery in v1.

## 7. When you're done with a phase

Self-check against the relevant SRS section's requirement IDs one by one before reporting it complete. "It looks done" is not enough — trace each FR to the code that implements it.
