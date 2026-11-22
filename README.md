# shrt — URL shortener

Fast, minimal URL shortener. FastAPI backend and React frontend, fully separated and talking only through a REST API.

## Test results

<!-- TESTS:START -->
_Last run: 2026-11-22 20:24 UTC_

| Suite | Tests | Passed | Failed | Time | Status |
|---|---|---|---|---|---|
| Backend (pytest) | 38 | 38 | 0 | 0.33s | ✅ pass |
| Frontend (vitest) | 8 | 8 | 0 | 0.41s | ✅ pass |
<!-- TESTS:END -->

Full report: [results/SUMMARY.md](results/SUMMARY.md) · regenerate with `./scripts/run_tests.sh` · CI runs the same script on every push ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Performance

Redirects run at ~4,100 req/s with 0 errors on a single machine (client and server sharing the CPU), about 85% of a no-op endpoint. Details: [results/BENCHMARK.md](results/BENCHMARK.md) · rerun with `backend/.venv/bin/python scripts/bench.py` against a running stack.

How the hot path stays fast:
- **Redis cache** for code → URL lookups; Postgres is only hit on a cache miss.
- **Buffered click counting:** a redirect does one Redis `HINCRBY`; a background task writes totals to Postgres in batches every 2s (atomic `RENAME` hand-off, so no click is lost or double-counted across workers; flushed on shutdown too).
- **nginx keeps a keepalive pool to the API.** Without it, load testing exhausted ephemeral ports and ~40% of requests returned 502.

## Architecture

```
browser ──► nginx (web)
             ├─ /, /assets/*         → static React build
             └─ /api/*, /{code}, /docs → FastAPI (api) ──► Redis (hot redirects)
                                                     └──► PostgreSQL (links)
```

- **Backend** (`backend/`): Python 3.14, FastAPI, SQLAlchemy 2 async, Postgres / SQLite, Redis / in-memory LRU cache.
- **Frontend** (`frontend/`): Vite, React 19, TypeScript, plain CSS with the Catppuccin Latte/Mocha palettes (follows system theme).
- Redirects are `302` + `no-store` so browsers don't cache them and every click reaches the server.

## API (v1)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/links` | body `{url, alias?, expires_in_days?}` → `201` link |
| `GET` | `/api/v1/links/{code}` | link info and click count |
| `GET` | `/{code}` | `302` to target · `404` unknown · `410` expired |
| `GET` | `/healthz` | liveness |

Interactive docs at `/docs`. Errors: `409` alias taken, `422` invalid input, `429` rate limited.

## Local development

No system packages needed beyond `uv`, `node`/`npm` and (for deployment) Docker.

```bash
# backend → http://localhost:8000
cd backend && uv sync && .venv/bin/uvicorn app.main:app --reload

# frontend → http://localhost:5173 (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

## Deploy

```bash
cp .env.example .env     # set POSTGRES_PASSWORD and BASE_URL (your public domain)
docker compose up -d --build
```

The app is served on `PORT` (default 8080). Put it behind a TLS-terminating proxy (Caddy, Traefik, Cloudflare) on any VPS.

## Configuration (backend env vars)

| Var | Default | |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | `postgresql+asyncpg://…` in prod |
| `REDIS_URL` | – | unset → in-process LRU cache |
| `BASE_URL` | `http://localhost:8000` | used to build `short_url` |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list |
| `CODE_LENGTH` | `7` | base62 → 3.5×10¹² codes |
| `RATE_LIMIT_PER_MINUTE` | `30` | link creations per IP (shared across workers via Redis) |
| `CLICK_FLUSH_SECONDS` | `2` | how often buffered clicks are written to the DB |
