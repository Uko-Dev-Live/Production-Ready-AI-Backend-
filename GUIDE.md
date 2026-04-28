# AI Backend — Complete Developer Guide

**A comprehensive walkthrough of a production-ready FastAPI + Celery + PostgreSQL + Alembic + MCP project.**

This guide assumes you are comfortable reading Python but not necessarily familiar with async SQLAlchemy, Celery, or containerised development. Every file and every command is explained. If something goes wrong, the troubleshooting section at the end covers every error encountered during development.

---

## Table of Contents

1. [What You're Building](#1-what-youre-building)
2. [Architecture at a Glance](#2-architecture-at-a-glance)
3. [Prerequisites](#3-prerequisites)
4. [Project Layout Explained](#4-project-layout-explained)
5. [Every Layer, Explained](#5-every-layer-explained)
6. [Environment Setup](#6-environment-setup)
7. [Running with Docker](#7-running-with-docker)
8. [Database Migrations with Alembic](#8-database-migrations-with-alembic)
9. [Importing the Fake Users](#9-importing-the-fake-users)
10. [Using the API](#10-using-the-api)
11. [Background Workers (Celery)](#11-background-workers-celery)
12. [Monitoring with Flower](#12-monitoring-with-flower)
13. [MCP Server](#13-mcp-server)
14. [AI Model Integration](#14-ai-model-integration)
15. [Running Tests](#15-running-tests)
16. [Makefile Reference](#16-makefile-reference)
17. [Common Problems and Fixes](#17-common-problems-and-fixes)
18. [Extending the Project](#18-extending-the-project)
19. [Deploying to Production](#19-deploying-to-production)

---

## 1. What You're Building

A small, production-shaped AI backend demonstrating every pattern a real platform team uses:

| Concern | Tool | Why this choice |
|---|---|---|
| Web framework | FastAPI 0.115 | Fastest mainstream Python framework, native async, auto OpenAPI docs |
| Input validation | Pydantic v2 | Compile-time type checking, clear error messages, JSON Schema export |
| Database | PostgreSQL 16 | Production-grade, JSON support, strong transactions |
| ORM | SQLAlchemy 2 (async) | The de-facto Python ORM; typed `Mapped[...]` API in v2 is excellent |
| Migrations | Alembic | Autogenerate from models, reversible, reviewable |
| Background jobs | Celery + Redis | Battle-tested distributed queue; Redis doubles as result backend |
| Task monitoring | Flower | Live dashboard, no extra config needed |
| AI integration | OpenAI SDK | With a built-in mock so the app runs without any API key |
| AI tool exposure | MCP server | Open standard for letting AI assistants call your backend |
| Containers | Docker + Compose | One command starts 6 services with correct networking |
| Secrets | pydantic-settings + .env | No secrets in code; dev and prod use identical loading |
| Auth | bcrypt + JWT (python-jose) | Industry standard, stateless, simple |
| Logging | structlog | JSON in production, pretty in dev, context-aware |
| Testing | pytest + httpx + aiosqlite | In-memory DB for unit tests, full HTTP exercising |

**Everything you need to run this is in the repository.** You do not need a Python installation on your host — all code runs inside containers.

---

## 2. Architecture at a Glance

```
┌──────────────────────┐
│   HTTP Client        │    (browser, curl, Postman)
│   (localhost:8000)   │
└───────────┬──────────┘
            │
            │ POST /jobs  + JWT
            ▼
┌──────────────────────┐     ┌──────────────────┐
│   FastAPI (api)      │────►│  PostgreSQL (db) │  ← stores users, jobs
│   - Pydantic schemas │     └──────────────────┘
│   - Async SQLAlchemy │
│   - JWT auth         │
└───────────┬──────────┘
            │ run_ai_job.delay(job_id)
            ▼
┌──────────────────────┐
│   Redis (redis)      │  ← broker + result backend
└───────────┬──────────┘
            │ polled by
            ▼
┌──────────────────────┐
│  Celery Worker       │  ← separate process
│  - AI engine         │     runs OpenAI calls (or mock)
│  - Updates DB status │
└──────────────────────┘

┌──────────────────────┐     ┌──────────────────┐
│  Flower (:5555)      │     │  MCP Server      │
│  monitors workers    │     │  (:9000)         │
└──────────────────────┘     └──────────────────┘
```

The point of separating the API from the worker is that **slow AI calls never block a user's HTTP request**. The API takes the request, drops a task onto Redis, and returns a `job_id` in milliseconds. The worker picks it up in the background.

---

## 3. Prerequisites

### System requirements
- **Linux** (guide written for Ubuntu), macOS, or WSL2 on Windows
- **Docker Engine 24+** with the **Docker Compose plugin**
- **make** (usually pre-installed)
- ~1 GB free disk space

### Installing Docker on Ubuntu

```bash
# Remove any old versions
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# Install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker's repository
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
                        docker-buildx-plugin docker-compose-plugin

# Run Docker without sudo
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version            # Docker version 24 or higher
docker compose version      # v2 or higher
```

---

## 4. Project Layout Explained

```
ai_backend/
│
├── .env.example             # Template for environment variables
├── .env                     # Your actual secrets (git-ignored)
├── .gitignore
├── .dockerignore
├── Dockerfile               # Multi-stage image: base → deps → app
├── docker-compose.yml       # Orchestrates 6 services
├── Makefile                 # All helper commands
├── alembic.ini              # Alembic configuration
├── pytest.ini               # Test runner configuration
├── requirements.txt         # Pinned Python dependencies
├── README.md                # Quick reference
├── GUIDE.md                 # This file
│
├── alembic/                 # Database migration system
│   ├── env.py               # Migration runner (sync engine + psycopg2)
│   └── versions/
│       └── 0001_initial_schema.py  # First migration: creates tables
│
├── app/                     # Application source code
│   ├── main.py              # FastAPI factory, router registration
│   │
│   ├── core/                # Framework-agnostic utilities
│   │   ├── config.py        # pydantic-settings Settings class
│   │   ├── logging.py       # structlog configuration
│   │   └── security.py      # bcrypt hashing + JWT creation/decode
│   │
│   ├── db/                  # Database plumbing
│   │   ├── base.py          # Defines Base = DeclarativeBase (only)
│   │   ├── models.py        # Registry: imports User + Job for Alembic
│   │   └── session.py       # Async engine + get_db() dependency
│   │
│   ├── models/              # SQLAlchemy ORM classes (= database tables)
│   │   ├── user.py          # User table
│   │   └── job.py           # Background-job table
│   │
│   ├── schemas/             # Pydantic classes (= API request/response shapes)
│   │   ├── user.py          # UserCreate, UserOut, TokenOut, ...
│   │   └── job.py           # JobCreate, JobOut, JobListOut
│   │
│   ├── services/            # Business logic — thin routes, fat services
│   │   ├── user_service.py  # Create, read, auth, update users
│   │   └── job_service.py   # Create jobs, update status, list jobs
│   │
│   ├── api/                 # HTTP layer
│   │   ├── deps.py          # get_current_user — JWT auth dependency
│   │   └── routes/
│   │       ├── auth.py      # POST /auth/register, /auth/login
│   │       ├── users.py     # GET/PATCH /users, /users/{id}, /users/me
│   │       └── jobs.py      # POST/GET /jobs
│   │
│   ├── workers/             # Celery background-task system
│   │   ├── celery_app.py    # Celery instance + queue config
│   │   ├── ai_tasks.py      # run_ai_job, send_welcome_email, health_check
│   │   └── ai_engine.py     # OpenAI wrapper with mock fallback
│   │
│   └── mcp/                 # Model Context Protocol server
│       └── server.py        # 3 tools: get_user_info, list_jobs, run_ai_analysis
│
├── scripts/
│   ├── fake_users.csv       # 30 realistic test users
│   └── import_users.py      # Idempotent bulk loader
│
├── monitoring/
│   ├── flower.conf          # Flower configuration
│   └── README.md            # Monitoring how-to
│
└── tests/
    ├── conftest.py          # Shared pytest fixtures
    ├── test_health.py       # Smoke tests
    ├── test_auth.py         # Registration + login
    └── test_ai_engine.py    # AI engine unit tests (mocked)
```

### Why this layout?

This follows the **layered architecture** pattern:

```
Route  (HTTP)  →  Service  (business logic)  →  Model  (database)
Schema (Pydantic validation wrapping routes)
```

Keeping these concerns separate means each file has one reason to change. When you add a new endpoint, you modify the route. When you change a database column, you edit the model and add a migration. When business rules change, you touch the service. The schemas define contracts that protect you from accidentally returning sensitive fields like `hashed_password`.

---

## 5. Every Layer, Explained

### 5.1 Configuration — `app/core/config.py`

`Settings` is a Pydantic model that reads environment variables at startup.

```python
class Settings(BaseSettings):
    APP_NAME: str = "AI Backend"
    DATABASE_URL: str = "postgresql+asyncpg://..."
    OPENAI_API_KEY: str = "sk-placeholder"
    # ...

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",   # Ignore undeclared env vars — don't crash
    )
```

Every other module imports `from app.core.config import settings`. The `@lru_cache` on `get_settings()` ensures `.env` is parsed exactly once.

**Important detail:** `extra="ignore"` is set so that environment variables used by Docker (like `POSTGRES_PASSWORD`) don't cause Pydantic to raise `Extra inputs are not permitted` at startup. The `POSTGRES_*` fields are also explicitly declared as typed fields with defaults.

### 5.2 Logging — `app/core/logging.py`

Uses `structlog`:
- In development (`DEBUG=true`): pretty colour output with aligned columns.
- In production: one JSON object per log line, ready for ELK or Loki.

Every log entry can have context attached:

```python
logger.bind(user_id=42, request_id=abc).info("payment processed", amount=99.99)
```

### 5.3 Security — `app/core/security.py`

**Password hashing uses bcrypt directly** (not via passlib — passlib is unmaintained and breaks against modern bcrypt releases). Three functions, clear names:

```python
hash_password(plain)             # → bcrypt hash string
verify_password(plain, hashed)   # → True/False, constant-time
create_access_token(subject)     # → signed JWT
decode_token(token)              # → payload dict
```

A helper `_to_bcrypt_bytes()` enforces bcrypt's hard 72-byte input limit by truncating — so absurdly long inputs get a predictable hash rather than a confusing error.

### 5.4 Database — `app/db/`

**`base.py`** defines only the SQLAlchemy base class. Nothing else. This is important to avoid circular imports.

```python
class Base(DeclarativeBase):
    pass
```

**`models.py`** is the model registry. It exists for two reasons:
1. Alembic imports it to discover every table for autogenerate.
2. Standalone scripts (like `import_users.py`) import it to load all models into SQLAlchemy's mapper registry so relationship strings like `relationship("Job", ...)` resolve correctly.

**`session.py`** creates an **async** engine backed by `asyncpg`:

```python
engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

`get_db()` is a FastAPI dependency. Every route that injects `Depends(get_db)` gets its own transactional session that commits on success and rolls back on error. You never write `session.commit()` yourself.

### 5.5 Models — `app/models/`

SQLAlchemy 2 uses typed class attributes:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # ...
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user")
```

The `"Job"` string is a **forward reference** — it avoids a circular import between `user.py` and `job.py`. SQLAlchemy resolves it at mapper-init time, provided both classes have been loaded into the registry (which is why `app/db/models.py` exists).

### 5.6 Schemas — `app/schemas/`

Pydantic classes that describe the shape of data crossing the API boundary:

```python
class UserCreate(BaseModel):          # what the client sends
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserOut(BaseModel):             # what the API returns
    id: int
    email: EmailStr
    # notice: hashed_password is NOT here — it can never leak
    model_config = {"from_attributes": True}
```

`from_attributes=True` lets Pydantic read values off of SQLAlchemy ORM objects (instead of requiring dictionaries).

### 5.7 Services — `app/services/`

Pure business logic. No HTTP concepts, no request/response objects:

```python
class UserService:
    async def create_user(self, db, data: UserCreate) -> User:
        if await self.get_by_email(db, data.email):
            raise ValueError("Email already registered")
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            # ...
        )
        db.add(user)
        await db.flush()
        return user
```

### 5.8 Routes — `app/api/routes/`

Thin wrappers that hand off to services:

```python
@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user = await user_service.create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    send_welcome_email.delay(user.email, user.username)  # fire Celery task
    return user
```

### 5.9 Workers — `app/workers/`

**`celery_app.py`** creates the Celery instance:

```python
celery_app = Celery(
    "ai_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.ai_tasks"],
)
```

**`ai_tasks.py`** defines tasks decorated with `@celery_app.task`. When the API calls `run_ai_job.delay(job_id)`, Celery serialises the arguments as JSON, pushes the message onto Redis, and returns a task UUID. A separate worker process picks it up and runs the function.

**Tasks run in a separate process** from FastAPI. No FastAPI request context exists. We create sync SQLAlchemy sessions manually.

**`ai_engine.py`** wraps OpenAI's chat-completions API with a mock fallback:

```python
class AIEngine:
    def run(self, job_type: str, input_text: str) -> dict:
        if self._client:                       # real OpenAI client
            return self._call_openai(job_type, input_text)
        return self._mock_response(job_type, input_text)   # deterministic mock
```

If `OPENAI_API_KEY` is missing or placeholder, the mock path is used — the entire async pipeline works without any external API calls.

### 5.10 MCP Server — `app/mcp/server.py`

Exposes three tools to AI assistants:
- `get_user_info(username)` — look up a user from PostgreSQL
- `list_recent_jobs(user_id, limit)` — list a user's jobs
- `run_ai_analysis(job_type, input_text)` — run an AI job inline

Runs on port 9000. If the `mcp` package isn't installed, a small FastAPI fallback server exposes the same tools via HTTP.

---

## 6. Environment Setup

```bash
# Enter the project
cd ai_backend

# Create your .env from the template
cp .env.example .env

# Review it
cat .env
```

The template looks like this:

```bash
# Application
APP_ENV=development
SECRET_KEY=supersecretkey-change-in-production-please

# PostgreSQL
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=aibackend
POSTGRES_USER=aiuser
POSTGRES_PASSWORD=aipassword

# Async DSN (asyncpg) — used by SQLAlchemy at runtime
DATABASE_URL=postgresql+asyncpg://aiuser:aipassword@db:5432/aibackend

# Sync DSN (psycopg2) — used by Alembic migrations & Celery worker
SYNC_DATABASE_URL=postgresql://aiuser:aipassword@db:5432/aibackend

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# AI / OpenAI
OPENAI_API_KEY=sk-your-openai-key-here
AI_MODEL=gpt-4o-mini
AI_MAX_TOKENS=1024
```

**Two database URLs?** Yes — SQLAlchemy runtime needs the async `asyncpg` driver, but Alembic migrations run synchronously and need `psycopg2`. The schemes (`postgresql+asyncpg://` vs `postgresql://`) tell SQLAlchemy which driver to load. Mixing them up produces the classic error `The asyncio extension requires an async driver to be used`.

**Hostnames `db` and `redis`** are Docker's internal service names — they resolve automatically within the Compose network. Don't change them.

---

## 7. Running with Docker

```bash
# Start every service in the background
make up
```

First run takes 2–3 minutes to download images and install Python packages. Subsequent runs start in a few seconds.

Verify all six services are healthy:

```bash
docker compose ps
```

Expected output:

```
NAME               STATUS              PORTS
aibackend_api      Up 30s (healthy)    0.0.0.0:8000->8000/tcp
aibackend_db       Up 30s (healthy)    0.0.0.0:5432->5432/tcp
aibackend_flower   Up 25s              0.0.0.0:5555->5555/tcp
aibackend_mcp      Up 25s              0.0.0.0:9000->9000/tcp
aibackend_redis    Up 30s (healthy)    0.0.0.0:6379->6379/tcp
aibackend_worker   Up 25s
```

Service URLs:

| URL | Purpose |
|---|---|
| http://localhost:8000 | API root (returns a welcome JSON) |
| http://localhost:8000/docs | Swagger UI — interactive API explorer |
| http://localhost:8000/redoc | ReDoc — clean API reference |
| http://localhost:8000/health | Liveness probe for monitoring systems |
| http://localhost:5555 | Flower — Celery dashboard |
| http://localhost:9000 | MCP tool server (HTTP fallback mode) |

---

## 8. Database Migrations with Alembic

Migrations are versioned SQL change scripts. Every time you change a model (add a column, rename a field, change a type), you generate a migration and commit it alongside the code.

### Apply the initial migration

```bash
make migrate
```

This runs `alembic upgrade head` inside the API container. Expected output:

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial schema
✅  Migrations applied
```

### Creating a new migration

Say you add a `phone` column to `User`:

```python
# app/models/user.py
phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

Then run:

```bash
make makemigration MSG="add phone to users"
```

This runs `alembic revision --autogenerate -m "add phone to users"`. It compares `Base.metadata` against the live database and creates a new file:

```
alembic/versions/0002_add_phone_to_users.py
```

**Always review the generated file.** Autogenerate is excellent but not perfect — it can miss complex changes like table renames. Then apply:

```bash
make migrate
```

### Other migration commands

```bash
# Show current state
docker compose exec api alembic current

# Show full history
docker compose exec api alembic history

# Roll back one migration
make downgrade

# Roll back all (dangerous — wipes schema)
docker compose exec api alembic downgrade base
```

### How Alembic is wired internally

`alembic/env.py` does three things:
1. Imports `settings` from `app.core.config` to get the database URL.
2. Imports `target_metadata` from `app.db.models` — which in turn loads every model class.
3. Creates a **sync** SQLAlchemy engine using `SYNC_DATABASE_URL` (psycopg2).

Alembic is a one-shot CLI tool, so it doesn't need asyncio. Using a sync engine keeps the code simpler and avoids the `The asyncio extension requires an async driver` error that comes from accidentally mixing sync URLs with async engines.

---

## 9. Importing the Fake Users

The project ships with 30 realistic test users in `scripts/fake_users.csv`. Each has a login password of `Password123!`.

```bash
make import-users
```

Output:

```
[INFO] Found 30 rows in fake_users.csv
  [ADD]   alice.johnson@example.com (Alice Johnson)
  [ADD]   bob.smith@example.com (Bob Smith)
  ...
──────────────────────────────────────────────────
  ✅  Created : 30
  ⏭   Skipped : 0  (already exist)
──────────────────────────────────────────────────
```

### Key properties of the import script

- **Idempotent** — re-running it skips rows that already exist by email.
- **Uses bcrypt** — each password is hashed before insert.
- **Transactional** — all 30 inserts commit as one transaction.
- **Has `sys.path` fix at the top** — so `from app.* import ...` works when the script is invoked as `python scripts/import_users.py`.
- **Imports `app.db.models`** — so SQLAlchemy sees both `User` and `Job` classes and can resolve the `relationship("Job", ...)` string reference.

### Adding more test users

Just append rows to `scripts/fake_users.csv` and run `make import-users` again. Existing rows are skipped, new rows added.

---

## 10. Using the API

### Interactive documentation

Open http://localhost:8000/docs — Swagger UI lets you try every endpoint without leaving the browser.

### Manual walkthrough with curl

**Step 1 — Register**

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "username": "yourname",
    "full_name": "Your Full Name",
    "password": "StrongPass1!"
  }' | python3 -m json.tool
```

Response (201 Created):
```json
{
  "id": 31,
  "email": "you@example.com",
  "username": "yourname",
  "full_name": "Your Full Name",
  "role": "user",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-06-15T10:30:00+00:00"
}
```

**Step 2 — Log in and save the token**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"StrongPass1!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: ${TOKEN:0:40}..."
```

**Step 3 — Fetch your profile**

```bash
curl -s http://localhost:8000/users/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Step 4 — Submit an AI job**

```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "summarise",
    "input_data": "FastAPI is a modern, fast web framework for building APIs with Python 3.8+ based on standard Python type hints."
  }')

echo $RESPONSE | python3 -m json.tool
JOB_ID=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Job ID: $JOB_ID"
```

Response (202 Accepted — the worker hasn't started yet):
```json
{
  "id": 1,
  "status": "pending",
  "job_type": "summarise",
  "celery_task_id": "9f3c4b2a-...",
  "result": null,
  "created_at": "2024-06-15T10:31:00+00:00"
}
```

**Step 5 — Poll for the result**

```bash
# Wait for the worker, then fetch
sleep 3
curl -s http://localhost:8000/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Response (status now `completed`):
```json
{
  "id": 1,
  "status": "completed",
  "result": {
    "summary": "FastAPI is a high-performance Python web framework...",
    "key_points": ["Based on Python type hints", "Very fast", "Modern"],
    "word_count": 22,
    "_meta": {"model": "mock", "tokens": 0}
  },
  "started_at": "2024-06-15T10:31:01+00:00",
  "completed_at": "2024-06-15T10:31:03+00:00"
}
```

### Complete endpoint list

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | — | Welcome JSON |
| GET | `/health` | — | Liveness probe |
| POST | `/auth/register` | — | Create account |
| POST | `/auth/login` | — | Get JWT token |
| GET | `/users/me` | ✅ | Own profile |
| GET | `/users` | ✅ | List all users (paginated) |
| GET | `/users/{id}` | ✅ | Get user by ID |
| PATCH | `/users/{id}` | ✅ | Update own profile |
| POST | `/jobs` | ✅ | Submit AI job |
| GET | `/jobs` | ✅ | List your jobs |
| GET | `/jobs/{id}` | ✅ | Poll job status |
| GET | `/jobs/{id}/raw` | ✅ | Raw Celery task state (debug) |

---

## 11. Background Workers (Celery)

### The event-driven flow

```
1. Client POSTs to /jobs
         │
2. FastAPI inserts Job row (status=pending) via async SQLAlchemy
         │
3. FastAPI calls run_ai_job.delay(job_id)
     → Celery serialises [job_id] as JSON
     → Pushes the message onto Redis queue "ai"
     → Returns a task UUID immediately
         │
4. FastAPI attaches task UUID to the Job row, returns 202 to client
         │
         │  ─── Meanwhile, in a SEPARATE process ─────
         ▼
5. Celery worker polls the Redis queue, picks up the message
         │
6. Worker calls run_ai_job(job_id)
     → Updates Job.status = "running"
     → Calls AIEngine.run(job_type, input_data)
     → Updates Job.status = "completed", Job.result = {...}
         │
7. Client polls GET /jobs/{id} → sees the result
```

### Viewing worker logs

```bash
make logs-worker
# or
docker compose logs -f worker
```

Expected output when a job runs:

```
[INFO] Task started [task_id=9f3c4b2a...] [job_id=1]
[INFO] Task completed [task_id=9f3c4b2a...] [job_id=1] [job_type=summarise]
```

### Scaling workers horizontally

```bash
# Run 3 worker containers
docker compose up -d --scale worker=3
```

Each worker processes tasks from the same Redis queue. More workers = higher throughput.

### Triggering tasks manually

Useful for testing:

```bash
make shell

python3 << 'EOF'
from app.workers.ai_tasks import health_check, send_welcome_email

# Test health check
result = health_check.delay()
print("Task ID:", result.id)

# Test welcome email
email_task = send_welcome_email.delay("test@example.com", "testuser")
import time; time.sleep(2)
print("Email result:", email_task.result)
EOF
```

### Queue configuration

In `celery_app.py`:

```python
task_routes={
    "app.workers.ai_tasks.run_ai_job": {"queue": "ai"},
    "app.workers.ai_tasks.send_welcome_email": {"queue": "email"},
},
```

Different task types go to different queues. You can dedicate workers per queue:

```bash
# Worker that only handles AI tasks
celery -A app.workers.celery_app worker -Q ai --loglevel=info

# Worker that only handles emails
celery -A app.workers.celery_app worker -Q email --loglevel=info
```

---

## 12. Monitoring with Flower

**Open http://localhost:5555** after `make up`.

### Tabs to know

| Tab | What it shows |
|---|---|
| Dashboard | Worker list with status, task rates, memory |
| Tasks | Every task ever run — args, result, runtime, worker, state |
| Broker | Redis queue depths (pending + active per queue) |
| Monitor | Real-time graph of tasks per second |

### Terminal commands

```bash
# Active tasks right now
make watch-tasks

# Registered tasks (what the worker knows how to run)
docker compose exec api celery -A app.workers.celery_app inspect registered

# Worker statistics
docker compose exec api celery -A app.workers.celery_app inspect stats

# Check Redis queue depth directly
docker compose exec redis redis-cli LLEN celery
docker compose exec redis redis-cli LLEN ai

# Purge all pending tasks (CAUTION — lost forever)
docker compose exec api celery -A app.workers.celery_app purge
```

---

## 13. MCP Server

Model Context Protocol is an open standard for giving AI assistants access to external tools and data. The project's MCP server (`app/mcp/server.py`) exposes three tools:

| Tool | Purpose |
|---|---|
| `get_user_info(username)` | Look up a user by username from PostgreSQL |
| `list_recent_jobs(user_id, limit)` | Return the N most recent jobs for a user |
| `run_ai_analysis(job_type, input_text)` | Run an AI job synchronously |

### Connecting Claude Desktop

Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-backend": {
      "command": "docker",
      "args": [
        "compose",
        "-f", "/absolute/path/to/ai_backend/docker-compose.yml",
        "exec", "-T", "mcp",
        "python", "-m", "app.mcp.server"
      ]
    }
  }
}
```

Restart Claude Desktop. You can now ask Claude: *"What jobs has alice_j submitted recently?"* — Claude will call `list_recent_jobs` against your database.

### Testing the HTTP fallback

If the `mcp` Python package isn't available, the server runs a plain FastAPI fallback on port 9000:

```bash
curl -s "http://localhost:9000/tools/get_user_info?username=alice_j" \
  | python3 -m json.tool

curl -s -X POST "http://localhost:9000/tools/run_ai_analysis" \
  -H "Content-Type: application/json" \
  -d '{"job_type": "sentiment", "input_text": "I love this project!"}' \
  | python3 -m json.tool
```

---

## 14. AI Model Integration

### Mock mode (default — no API key required)

When `OPENAI_API_KEY` is missing or contains the placeholder `sk-your-...`, the AI engine uses deterministic mock responses. This lets the full event-driven flow work end-to-end without any external API calls — great for testing routing, background tasks, and UI.

### Connecting to OpenAI

1. Get an API key at https://platform.openai.com/api-keys
2. Put it in `.env`:
   ```
   OPENAI_API_KEY=sk-proj-real-key-here
   AI_MODEL=gpt-4o-mini
   AI_MAX_TOKENS=1024
   ```
3. Restart the worker and MCP server (they load `.env` at process start):
   ```bash
   docker compose restart worker mcp
   ```

### Adding a new job type

Say you want a `"translate"` job.

**1. Add a system prompt** in `app/workers/ai_engine.py`:

```python
SYSTEM_PROMPTS = {
    # ... existing types ...
    "translate": (
        "You are a translation assistant. "
        "Return JSON: {\"translated_text\": \"...\", "
        "\"source_language\": \"...\", \"target_language\": \"...\"}. "
        "JSON only, no markdown."
    ),
}
```

**2. Add a mock response** in `_mock_response()`:

```python
"translate": {
    "translated_text": "[MOCK] Esto es una traducción simulada.",
    "source_language": "en",
    "target_language": "es",
    "_meta": {"model": "mock", "job_type": "translate", "tokens": 0},
},
```

**3. That's it.** Submit jobs with `"job_type": "translate"` immediately. No schema or route changes needed.

### Chained jobs — output of one job fed to another

```bash
# Job 1: classify the topic
JOB1=$(curl -s -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"job_type":"classify","input_data":"Bitcoin reached a new all-time high today."}')
JOB1_ID=$(echo $JOB1 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

sleep 4

# Read the category
CATEGORY=$(curl -s http://localhost:8000/jobs/$JOB1_ID \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['category'])")

# Job 2: generate commentary based on the category
curl -s -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"job_type\":\"generate\",\"input_data\":\"Write 3 sentences of expert commentary on a $CATEGORY news story.\"}" \
  | python3 -m json.tool
```

### Swapping to Anthropic or a local model

Replace `_call_openai()` with your provider's SDK. The `run()` method doesn't change — every consumer of the engine gets the same interface.

---

## 15. Running Tests

```bash
# Full suite inside Docker
make test

# Specific file
docker compose exec api pytest tests/test_auth.py -v

# With full stdout (don't capture prints)
docker compose exec api pytest tests/ -v -s

# Only AI engine tests (fast, no DB)
docker compose exec api pytest tests/test_ai_engine.py -v
```

### Test file overview

| File | Covers |
|---|---|
| `test_health.py` | `/health` and `/` return correct JSON |
| `test_auth.py` | Register, duplicate email conflict, login, wrong password, protected routes |
| `test_ai_engine.py` | All four job types return correct keys; invalid types raise ValueError |

### How tests are isolated

`tests/conftest.py` provides two fixtures:

- **`db_session`** — a fresh in-memory SQLite database per test function, created and destroyed cleanly.
- **`client`** — an `httpx.AsyncClient` bound to the FastAPI app, with `get_db` overridden to use the test session.

No Docker or PostgreSQL required for unit tests — they run in milliseconds.

---

## 16. Makefile Reference

Every command runs `docker compose exec api ...` or `docker compose ...` under the hood.

| Command | What it does |
|---|---|
| `make up` | Start all services in the background |
| `make down` | Stop all services (preserve volumes) |
| `make build` | Rebuild images from scratch (`--no-cache`) |
| `make reset` | `clean` + `build` + `up` + `migrate` + `import-users` |
| `make logs` | Tail logs from all services |
| `make logs-api` | Tail only the API logs |
| `make logs-worker` | Tail only the Celery worker logs |
| `make shell` | bash shell inside the API container |
| `make shell-db` | psql shell inside the PostgreSQL container |
| `make migrate` | Apply all pending Alembic migrations |
| `make makemigration MSG="..."` | Auto-generate a new migration |
| `make migration-status` | Show current migration revision |
| `make downgrade` | Roll back the last migration |
| `make import-users` | Load `scripts/fake_users.csv` |
| `make watch-tasks` | Show active Celery tasks |
| `make flower` | Open Flower in default browser |
| `make test` | Run pytest suite |
| `make clean` | Remove containers and volumes (data lost!) |
| `make help` | Print this list with descriptions |

---

## 17. Common Problems and Fixes

These are the real errors encountered while building this project, documented so you can cross-reference if you hit the same thing.

### A. Dependency resolution fails during `make build`

**Symptom:** `ERROR: Cannot install ... because these package versions have conflicting dependencies` during `pip install`.

**Cause:** Two packages want incompatible versions of a shared dependency (for example, `fastapi==0.115.0` needs `starlette<0.39` but `mcp==1.0.0` needs `starlette>=0.39`).

**Fix:** Use the pinned versions in the shipped `requirements.txt`. Every pin has been verified to resolve cleanly. If you bump a version, bump its compatible siblings too.

### B. Pydantic `Extra inputs are not permitted` at startup

**Symptom:**
```
pydantic_core.ValidationError: ... Extra inputs are not permitted
POSTGRES_HOST: Extra inputs are not permitted
```

**Cause:** Pydantic v2 `BaseSettings` defaults to rejecting unknown env vars. Your `.env` has vars not declared as fields on `Settings`.

**Fix:** The current `config.py` declares every `POSTGRES_*` field explicitly **and** sets `extra="ignore"` in `model_config` — so future new env vars won't break startup.

### C. Alembic: `asyncio extension requires an async driver`

**Symptom:**
```
sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async
driver to be used. The loaded 'psycopg2' is not async.
```

**Cause:** Mixing sync DSN (`postgresql://`) with async engine, or vice versa.

**Fix:** The shipped `alembic/env.py` uses `create_engine()` (sync) with `settings.SYNC_DATABASE_URL`. Don't introduce `async_engine_from_config` here — Alembic is synchronous by design.

### D. Circular import: `cannot import name 'User' from partially initialized module`

**Symptom:** ImportError while loading `app/models/user.py` or `app/db/base.py`.

**Cause:** `db/base.py` and `models/user.py` tried to import each other.

**Fix:** The shipped layout has:
- `db/base.py` — defines `Base` only, imports nothing else from app.
- `db/models.py` — imports every model (registry).
- Models import only `Base` from `db/base.py`.

If you add a new model, add one line to `app/db/models.py` — don't touch `base.py`.

### E. `ModuleNotFoundError: No module named 'app'` when running a script

**Symptom:** Happens in `python scripts/import_users.py`.

**Cause:** Python only adds the script's own directory (`/app/scripts`) to `sys.path`, not the project root `/app`.

**Fix:** The shipped `import_users.py` prepends the project root to `sys.path` as its very first action. For any new script, include the same four-line pattern at the top before any `from app...` import.

### F. `expression 'Job' failed to locate a name`

**Symptom:** SQLAlchemy error when querying Users — specifically `Mapper[User(users)]` failing on the `jobs` relationship.

**Cause:** The `User` model's `relationship("Job", ...)` uses a string forward reference. SQLAlchemy resolves it at mapper-init time by searching its registry. If nothing has imported `Job`, the registry doesn't contain it.

**Fix:** Any standalone script that uses the ORM must import `app.db.models` (which loads both User and Job). This is already done in the shipped `import_users.py`.

### G. bcrypt errors: `module 'bcrypt' has no attribute '__about__'` or `password cannot be longer than 72 bytes`

**Symptom:** Both errors at once during `make import-users`.

**Cause:** `passlib` (an unmaintained library, last release 2020) broke against modern bcrypt 4.1+ releases.

**Fix:** The shipped `security.py` uses **bcrypt directly**, dropping passlib entirely. Passwords are UTF-8 encoded and truncated to the 72-byte bcrypt limit explicitly. `requirements.txt` pins `bcrypt==4.2.0` and has no `passlib` line.

### H. Container can't connect to database

**Symptom:** `connection refused` errors in API logs on first start.

**Cause:** The API container starts before PostgreSQL is fully ready.

**Fix:** `docker-compose.yml` uses a `healthcheck:` on the `db` service, and `api` has `depends_on: db: condition: service_healthy`. If you still see this, run:

```bash
docker compose restart api
```

### I. Worker ignores new code

**Symptom:** You edit `ai_tasks.py` but the worker still runs the old version.

**Cause:** Celery workers load tasks at startup. File changes don't auto-reload.

**Fix:**
```bash
docker compose restart worker
```

### J. Total reset after schema or dependency overhaul

When in doubt, start fresh:

```bash
make clean     # remove containers AND volumes (wipes DB)
make build     # rebuild images (installs fresh Python deps)
make up        # start services
make migrate   # apply migrations
make import-users
```

Or the one-liner: `make reset`.

---

## 18. Extending the Project

### Add a new database table

1. Create `app/models/my_table.py` — define the ORM class inheriting from `Base`.
2. Add one line to `app/db/models.py`: `from app.models.my_table import MyTable`.
3. Generate a migration: `make makemigration MSG="add my_table"`.
4. Review the generated migration file.
5. Apply: `make migrate`.

### Add a new API endpoint

1. Create `app/schemas/my_feature.py` with Pydantic classes.
2. Create `app/services/my_feature_service.py` with the business logic.
3. Create `app/api/routes/my_feature.py` with route handlers.
4. Register the router in `app/main.py`: `app.include_router(my_feature.router)`.
5. (Optional) Add tests under `tests/`.

### Add a new Celery task

1. Open `app/workers/ai_tasks.py` (or create a new module and add it to the `include=[...]` list in `celery_app.py`).
2. Define the function with `@celery_app.task(name="...")`.
3. Call it from anywhere: `my_task.delay(arg1, arg2)`.
4. Restart the worker: `docker compose restart worker`.

### Add a new MCP tool

Edit `app/mcp/server.py`:
1. Write a Python function implementing the tool logic.
2. Add a new `mcp_types.Tool` entry inside `list_tools()`.
3. Add a new `elif name == "your_tool":` branch inside `call_tool()`.
4. Restart the MCP service: `docker compose restart mcp`.

---

## 19. Deploying to Production

The development setup needs several hardening steps before serving real traffic.

### Essential changes

1. **Secrets**: move `.env` values into a secrets manager (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault). The app reads the same env var names regardless of source.

2. **Replace these insecure defaults**:
   ```
   SECRET_KEY=<use `python -c "import secrets; print(secrets.token_urlsafe(32))"`>
   POSTGRES_PASSWORD=<use a 32-char random password>
   DEBUG=false
   APP_ENV=production
   ```

3. **Remove `--reload` from uvicorn**. Use multiple workers:
   ```dockerfile
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
   ```

4. **Restrict CORS** in `app/main.py`:
   ```python
   allow_origins=["https://your-real-domain.com"]
   ```

5. **Put a reverse proxy in front** (nginx, Traefik, Caddy) with TLS termination.

6. **Scale workers**:
   ```bash
   docker compose up -d --scale worker=5
   ```

7. **Database backups**: schedule `pg_dump` via cron or use your cloud provider's managed Postgres service.

8. **Redis persistence**: add `appendonly yes` to the Redis config if losing in-flight tasks is unacceptable.

9. **Observability**:
   - Ship JSON logs to ELK, Loki, or Datadog.
   - Scrape Prometheus metrics from Flower (`/metrics` endpoint).
   - Add distributed tracing (OpenTelemetry).

10. **Remove the mock AI fallback in production** — you want a hard error if `OPENAI_API_KEY` is missing, not silent mocks.

### Docker Compose → Kubernetes

The project maps cleanly to Kubernetes:
- `api`, `worker`, `mcp`, `flower` → Deployments
- `db`, `redis` → StatefulSets (or managed services)
- Migrations → an initContainer or one-shot Job that runs `alembic upgrade head`
- `.env` values → ConfigMap (non-secret) + Secret (passwords, API keys)

The code itself requires zero changes between development, staging, and production — only the environment variables differ.

---

## Final Notes

Every file in this project is small on purpose. If a class or function grows past ~100 lines, split it. If a route grows logic, push it into a service. If a service needs database work, do it through SQLAlchemy sessions. Keep the layers thin and the responsibilities clear — that's what makes a codebase pleasant to work in three years later.

For any file, you can open it directly and read top-to-bottom — the header docstring explains what the file does and why. When adding new code, keep that habit going.
