# Expense Tracker (v1)

A full-stack, multi-user personal expense tracker with bill splitting, savings goals, monthly budgets, and export capabilities.

## Overview

- **Backend:** FastAPI (Python 3.12 / 3.13), SQLAlchemy 2.x (ORM-only, no raw SQL), Alembic migrations, PostgreSQL, Argon2 password hashing, JWT authentication (15m access, 7d rotating refresh), slowapi rate limiting.
- **Frontend:** React + Vite + TypeScript (Node 24+), Tailwind CSS with custom "Saffron" design system, TanStack Query, React Router, Recharts, React Hook Form + Zod.
- **Data Model Rules:** Whole-rupee integers only (`INR`), non-negative balance invariant enforced via checks and database transactions with row locking.

---

## Repository Structure

```
.
├── backend/            # FastAPI app, SQLAlchemy models, Alembic migrations
│   ├── .env.example    # Backend environment template
│   ├── Dockerfile      # Production-ready backend Dockerfile
│   ├── entrypoint.sh   # Container entrypoint applying Alembic migrations
│   └── requirements.txt
├── frontend/           # React + Vite TypeScript SPA
│   ├── .env.example    # Frontend environment template
│   └── package.json
├── docs/               # Project specifications and guidelines
│   ├── SRS.md          # Software Requirements Specification (v1.0.0)
│   ├── ACCEPTANCE_TESTING.md
│   └── ANTIGRAVITY_PROMPT.md
├── docker-compose.yml  # Docker Compose orchestration for Backend & PostgreSQL
├── .dockerignore       # Docker build exclusions
├── .env.example        # Root environment template for Docker Compose
├── CHANGELOG.md        # Release and unreleased tracking
├── README.md           # Setup and project documentation
└── .gitignore
```

---

## Running with Docker Compose (Recommended)

Docker Compose runs the backend and an isolated PostgreSQL 16 database with persistent storage and automated Alembic schema migrations.

### Prerequisites

1. **Docker:** Docker Desktop (Windows/macOS) or Docker Engine v20.10+ (Linux)
2. **Docker Compose:** v2.20+ (included with modern Docker Desktop)

### 1. Configuration

Copy the root environment template:

```bash
cp .env.example .env
```

*(Optional)* Review `.env` if you wish to customize passwords, ports, or secrets. By default, standard development placeholders are provided.

### 2. Start the Application

Build the backend image and start the PostgreSQL and backend containers in detached mode:

```bash
docker compose up -d --build
```

Docker Compose will:
1. Start the PostgreSQL container (`expense_tracker_postgres`) and wait until its health check passes (`pg_isready`).
2. Start the backend container (`expense_tracker_backend`), run `alembic upgrade head` to apply all database migrations, and launch Uvicorn.

### 3. Verify Container Status

```bash
docker compose ps
```

Both `expense_tracker_backend` and `expense_tracker_postgres` should show status `Up` with `(healthy)`.

- **Backend API & Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

### 4. Viewing Logs

To stream live logs from all services:
```bash
docker compose logs -f
```

To view logs from the backend only:
```bash
docker compose logs -f backend
```

To view logs from PostgreSQL only:
```bash
docker compose logs -f postgres
```

### 5. Accessing Local PostgreSQL

PostgreSQL is exposed on `localhost:5432` for external GUI clients (DBeaver, TablePlus, pgAdmin) or CLI:

- **Host:** `localhost` (from host machine) / `postgres` (from inside Docker network)
- **Port:** `5432`
- **Database:** `expense_tracker`
- **Username:** `postgres`
- **Password:** `postgres` (or whatever is set in `.env`)

Connect via `psql` directly inside the container:
```bash
docker compose exec postgres psql -U postgres -d expense_tracker
```

### 6. Rebuilding Containers

Whenever you modify backend code, dependencies, or migration scripts:

```bash
docker compose build backend
docker compose up -d
```

Or rebuild and recreate in one command:
```bash
docker compose up -d --build
```

### 7. Stopping the Application

To stop the running containers without losing database data:
```bash
docker compose stop
```

To take down containers and the internal network:
```bash
docker compose down
```

*Note: Database data is safely persisted in the named Docker volume `expense_tracker_postgres_data`. To wipe database data completely, run `docker compose down -v`.*

### 8. Troubleshooting Common Issues

- **Port 5432 Already in Use:**
  If you have a native PostgreSQL service already running locally on Windows/Linux on port 5432, you can map PostgreSQL to another host port (e.g. `5433`) in your `.env`:
  ```env
  POSTGRES_PORT=5433
  ```
- **Port 8000 Already in Use:**
  If a local backend process is already running on port 8000:
  ```env
  BACKEND_PORT=8001
  ```
- **Backend cannot reach PostgreSQL:**
  Ensure the backend connects using the Docker service name (`postgres`), not `localhost`. The `DATABASE_URL` in `docker-compose.yml` automatically configures this internal hostname:
  `postgresql+psycopg://postgres:postgres@postgres:5432/expense_tracker`.
- **Database Migrations failed on startup:**
  Check backend startup logs with `docker compose logs backend`. You can also manually re-run migrations inside the container:
  ```bash
  docker compose exec backend alembic upgrade head
  ```

---

## Local Development Setup (Without Docker)

Native local installations are also supported for development.

### Prerequisites

1. **Python:** 3.12.x or 3.13.x
2. **Node.js:** v20+ or v24+ and `npm`
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
