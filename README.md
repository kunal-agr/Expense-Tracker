# Expense Tracker (v1)

A full-stack, multi-user personal expense tracker with bill splitting, savings goals, monthly budgets, and export capabilities.

## Overview

- **Backend:** FastAPI (Python 3.13), SQLAlchemy 2.x (ORM-only, no raw SQL), Alembic migrations, PostgreSQL, Argon2 password hashing, JWT authentication (15m access, 7d rotating refresh), slowapi rate limiting.
- **Frontend:** React + Vite + TypeScript (Node 24+), Tailwind CSS with custom "Saffron" design system, TanStack Query, React Router, Recharts, React Hook Form + Zod.
- **Data Model Rules:** Whole-rupee integers only (`INR`), non-negative balance invariant enforced via checks and database transactions with row locking.

---

## Repository Structure

```
.
├── backend/            # FastAPI app, SQLAlchemy models, Alembic migrations
│   ├── .env.example    # Backend environment template
│   └── requirements.txt
├── frontend/           # React + Vite TypeScript SPA
│   ├── .env.example    # Frontend environment template
│   └── package.json
├── docs/               # Project specifications and guidelines
│   ├── SRS.md          # Software Requirements Specification (v1.0.0)
│   └── ANTIGRAVITY_PROMPT.md
├── CHANGELOG.md        # Release and unreleased tracking
├── README.md           # Setup and project documentation
└── .gitignore
```

---

## Local Development Setup

No Docker is used for v1. Native local installations only.

### Prerequisites

1. **Python:** 3.13.x (or 3.11+)
2. **Node.js:** v24.x (or v20+) and `npm`
3. **PostgreSQL:** Local PostgreSQL instance running on port 5432

---

### 1. Database Setup

Create a PostgreSQL database for local development:

```sql
CREATE DATABASE expense_tracker;
```

---

### 2. Backend Setup

1. Open a terminal and navigate to `backend/`:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create your local `.env` configuration from the template:
   ```bash
   cp .env.example .env
   ```
   *Note: Edit `.env` with your local database credentials. Never commit `.env`.*

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Interactive API documentation will be available at:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

---

### 3. Frontend Setup

1. Open another terminal and navigate to `frontend/`:
   ```bash
   cd frontend
   ```

2. Create your local `.env` configuration from the template:
   ```bash
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The application UI will be available at: `http://localhost:5173`

---

### 4. Scheduled Jobs (Local Testing)

The system includes a secured endpoint for recurring transaction runs, split expiry, and notification pruning:

```bash
curl -X POST http://localhost:8000/api/v1/internal/jobs/daily \
  -H "X-Cron-Secret: <your_CRON_SECRET>"
```

---

## Security & Secrets Policy

- Secret keys, database connection strings, and tokens must only live in `.env` files.
- `.env` files are ignored by git and must never be committed. Only `.env.example` templates with placeholder values are committed.
