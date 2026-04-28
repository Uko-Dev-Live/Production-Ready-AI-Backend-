# AI Backend

**A production-ready Python backend template combining FastAPI, Celery, PostgreSQL, Alembic, and MCP — fully containerised with Docker.**

Built to be a drop-in starting point for any team that wants async APIs, background AI jobs, and proper migrations from day one. Every layer is small, well-labelled, and explained so a developer coming from Django or Express can follow the whole flow in an afternoon.

---

## Highlights

| What | Why it matters |
|---|---|
| **FastAPI 0.115 + Pydantic v2** | Async routes with compile-time validation, auto-generated OpenAPI docs |
| **PostgreSQL 16 + SQLAlchemy 2 (async)** | Modern typed ORM, connection pooling, transactions via a single dependency |
| **Alembic** | Every schema change tracked as a reviewable migration file |
| **Celery + Redis** | Heavy AI calls never block HTTP requests — offloaded to workers |
| **Flower** | Live dashboard for Celery workers, queues, and task history |
| **MCP server** | Expose your data and AI capabilities as tools to Claude / GPT assistants |
| **OpenAI integration with mock fallback** | Runs end-to-end with **zero API key** for local development |
| **bcrypt + JWT** | Secure password hashing and stateless authentication |
| **structlog** | JSON logs in production, pretty logs in development |
| **pytest + httpx + in-memory SQLite** | Fast unit tests with no Docker dependency |
| **Makefile** | 17 one-word commands replace every `docker compose` invocation |

---

## Quick Start — 4 commands, 60 seconds

```bash
# 1. Enter the project and create your .env
cp .env.example .env

# 2. Build and start every service (API, DB, Redis, worker, Flower, MCP)
make up

# 3. Apply database migrations
make migrate

# 4. Import 30 fake test users from CSV
make import-users
```

Now open these in your browser:

| URL | What you'll see |
|---|---|
| http://localhost:8000/docs | Interactive Swagger UI — try every endpoint |
| http://localhost:8000/redoc | Clean API reference documentation |
| http://localhost:5555 | Flower — live Celery task dashboard |
| http://localhost:8000/health | JSON health check |

Test credentials (from the imported CSV):

```
Email:    alice.johnson@example.com
Password: Password123!
```

---

## Project Layout

```
ai_backend/
├── app/                        # All application code
│   ├── main.py                 # FastAPI app factory
│   ├── api/                    # HTTP routes + auth dependencies
│   ├── core/                   # Config, logging, security (bcrypt, JWT)
│   ├── db/                     # SQLAlchemy engine, session, model registry
│   ├── models/                 # ORM classes (User, Job)
│   ├── schemas/                # Pydantic request/response validators
│   ├── services/               # Business logic (thin routes, fat services)
│   ├── workers/                # Celery app + AI tasks + OpenAI wrapper
│   └── mcp/                    # Model Context Protocol server
│
├── alembic/                    # Database migrations
├── scripts/                    # CSV loader, seed data
├── monitoring/                 # Flower config + monitoring guide
├── tests/                      # pytest test suite
│
├── Dockerfile                  # Multi-stage image build
├── docker-compose.yml          # 6 services orchestrated
├── Makefile                    # Helper commands
├── requirements.txt            # Pinned Python dependencies
├── .env.example                # Template — copy to .env
├── GUIDE.md                    # Full step-by-step guide
└── README.md                   # You are here
```

---

## How it Flows

```
┌─────────────┐   HTTP POST /jobs   ┌──────────────┐
│   Client    │ ──────────────────► │   FastAPI    │
└─────────────┘                     └──────┬───────┘
                                           │ 1. Insert Job (status=pending) in PostgreSQL
                                           │ 2. run_ai_job.delay(job_id)
                                           ▼
                                    ┌──────────────┐
                                    │    Redis     │  ← Celery broker
                                    └──────┬───────┘
                                           │ queue message
                                           ▼
                                    ┌──────────────┐
                                    │ Celery       │
                                    │ Worker       │ ← Picks up job, calls AI engine
                                    └──────┬───────┘
                                           │
                                           ▼  Updates Job row: status=completed, result=…
                                    ┌──────────────┐
                                    │ PostgreSQL   │
                                    └──────────────┘

Client polls GET /jobs/{id} → sees the result once status == "completed"
```

---

## Core Commands

All commands run via `make`. No need to remember long `docker compose` invocations.

```bash
make up              # Start all 6 services
make down            # Stop all services
make build           # Rebuild Docker images (no-cache)
make reset           # Full wipe + rebuild + migrate + import-users

make migrate         # Apply pending migrations
make makemigration MSG="add column x"  # Generate a new migration
make downgrade       # Roll back one migration step

make import-users    # Load scripts/fake_users.csv
make test            # Run the full test suite

make shell           # bash shell inside the API container
make shell-db        # psql shell inside the PostgreSQL container

make logs            # Tail all service logs
make logs-api        # Only API logs
make logs-worker     # Only Celery worker logs

make watch-tasks     # Show active Celery tasks in terminal
make flower          # Open Flower dashboard in browser
```

Run `make` with no arguments to see the full list with descriptions.

---

## Environment Variables

All secrets and configuration live in `.env` (never committed). Copy `.env.example` to `.env` and adjust as needed. The most important variables:

```bash
# Database
POSTGRES_PASSWORD=aipassword        # Change for production!
DATABASE_URL=postgresql+asyncpg://aiuser:aipassword@db:5432/aibackend
SYNC_DATABASE_URL=postgresql://aiuser:aipassword@db:5432/aibackend

# Security
SECRET_KEY=supersecretkey-change-in-production-please

# AI (leave as placeholder for mock mode, or add your real key)
OPENAI_API_KEY=sk-your-openai-key-here
AI_MODEL=gpt-4o-mini

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

With a placeholder `OPENAI_API_KEY`, the AI engine automatically falls back to built-in mock responses — the entire async/worker pipeline works without any external API calls.

---

## Services Overview

When you run `make up`, six Docker services come alive:

| Service | Port | What it does |
|---|---|---|
| `api` | 8000 | FastAPI application, serves HTTP routes |
| `worker` | — | Celery worker process, runs AI jobs |
| `flower` | 5555 | Celery monitoring dashboard |
| `mcp` | 9000 | MCP tool server (for AI assistants) |
| `db` | 5432 | PostgreSQL 16 database |
| `redis` | 6379 | Message broker + Celery result backend |

All share a Docker network — they resolve each other by service name (`db`, `redis`) rather than IP.

---

## Testing

```bash
# Full suite inside Docker
make test

# Specific file
docker compose exec api pytest tests/test_auth.py -v

# Stream output live
docker compose exec api pytest tests/ -v -s
```

Tests use in-memory SQLite for speed — no Docker required for unit tests alone. The HTTP routes are exercised via `httpx.AsyncClient`.

---

## AI Integration

The AI engine in `app/workers/ai_engine.py` supports four job types out of the box:

- **`summarise`** — condense long text into bullet points
- **`sentiment`** — classify text as positive / negative / neutral
- **`classify`** — categorise into predefined domains
- **`generate`** — free-form text generation

Submit a job:

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"job_type":"summarise","input_data":"Your text here..."}'
```

The response returns immediately with a `job_id` and `status: "pending"`. Poll `GET /jobs/{id}` to watch the status progress: `pending → running → completed`, with the result attached as structured JSON.

Add a new job type by adding one prompt to `AIEngine.SYSTEM_PROMPTS` and one mock to `_mock_response()`. No route or schema changes needed.

---

## Database Migrations

Every schema change is a reviewable Python file in `alembic/versions/`. The first migration ships with the project — it creates the `users` and `jobs` tables.

```bash
# Apply all pending
make migrate

# Add a column to a model, then auto-generate:
make makemigration MSG="add phone to users"

# Check current revision
docker compose exec api alembic current

# Roll back one step
make downgrade
```

Alembic uses a **sync** engine (psycopg2) internally — migrations are a one-shot CLI tool and don't need asyncio. The runtime app uses the async engine (asyncpg).

---

## Documentation

- **`GUIDE.md`** — Comprehensive step-by-step walkthrough covering every layer, every file, every command, plus extended AI examples, MCP integration, and troubleshooting. Start here if you're new.
- **`monitoring/README.md`** — Deep dive on Flower and Celery monitoring.
- **http://localhost:8000/docs** — Live interactive API docs (generated from the code).

---

## Requirements

- **Docker Engine 24+** and the Docker Compose plugin
- **Make** (pre-installed on most Linux distros; `sudo apt-get install make` on Ubuntu)
- ~1 GB free disk for images + PostgreSQL volume

No Python installation on the host is required — everything runs in containers.

---

## Production Hardening Checklist

Before running this in any environment with real users, address the following:

- [ ] Replace `SECRET_KEY` with a cryptographically random value (32+ bytes)
- [ ] Replace `POSTGRES_PASSWORD` with a strong random password
- [ ] Restrict CORS in `app/main.py` to your actual frontend origins
- [ ] Put the API behind a reverse proxy (nginx / Traefik) with TLS
- [ ] Drop `--reload` from uvicorn; use multiple workers (`--workers 4`)
- [ ] Load `.env` values from a secrets manager, not a file
- [ ] Set `DEBUG=false` and `APP_ENV=production`
- [ ] Configure log shipping (ELK, Grafana Loki, Datadog)
- [ ] Scale Celery workers horizontally (`docker compose up -d --scale worker=3`)
- [ ] Set up database backups and Redis persistence

---

## License

MIT — use, modify, and distribute freely.
