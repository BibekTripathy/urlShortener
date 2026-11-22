# Plan — urlShortener

## Goals
- Fast URL shortener: create short links, redirect with minimal latency, basic click stats.
- Backend and frontend fully separate; they talk **only** through a versioned REST API (`/api/v1`).
- Deployable with one command (`docker compose up -d`), no host-level packages (Python in `.venv` via `uv`, JS via local `npm`).
- Tests for both halves; results stored in `results/` and summarized in the README.

## Stack
| Layer | Choice | Why |
|---|---|---|
| API | Python 3.14, FastAPI, Pydantic v2, uvicorn | async, typed, auto OpenAPI docs at `/docs` |
| DB | PostgreSQL 17 (prod) / SQLite (dev, tests) via SQLAlchemy 2 async | same code, zero-setup locally |
| Cache | Redis 8 (prod) / in-process LRU (fallback) | hot redirects never touch the DB |
| Frontend | Vite + React 19 + TypeScript, plain CSS | small bundle, no UI framework bloat |
| Theme | Catppuccin — Mocha (dark) / Latte (light) via `prefers-color-scheme`; one accent (Mauve) | minimalist, consistent |
| Tests | pytest + httpx (backend), Vitest + Testing Library (frontend) | JUnit XML output |
| Deploy | Docker images + compose: postgres, redis, api, web (nginx) | nginx serves SPA, proxies `/api/*` and short codes to the API |

## API (v1)
- `POST /api/v1/links` `{url, alias?, expires_in_days?}` → `201 {code, short_url, url, created_at, expires_at, clicks}`
- `GET  /api/v1/links/{code}` → link info + clicks
- `GET  /{code}` → `302` redirect (302 not 301, so browsers don't cache and clicks are counted); `404` unknown, `410` expired
- `GET  /healthz` → `{status: "ok"}`

## Rules / edge cases
- Only `http`/`https`, max 2048 chars, must have host; reject links pointing back to our own domain (redirect loops).
- Codes: 7-char random base62 (`secrets`), retry on collision. Aliases: `[A-Za-z0-9_-]{3,32}`, reserved words (`api`, `docs`, `healthz`, `assets`…) blocked; uniqueness enforced by DB constraint → `409`.
- Per-IP rate limit on link creation (in-memory sliding window, configurable).
- Click count increment runs as a background task so the redirect returns immediately.
- CORS restricted to configured frontend origins.

## Layout
```
backend/   app/ (config, db, models, schemas, cache, routes), tests/, pyproject.toml, Dockerfile
frontend/  src/ (api client, components, theme css), tests, Dockerfile, nginx.conf
results/   backend-junit.xml, frontend-junit.xml, SUMMARY.md   (generated)
scripts/   run_tests.sh (runs both suites, writes results, updates README)
docker-compose.yml, .env.example, README.md
```

## Git
- `main` created empty-ish; all work on `dev`. Merge to `main` and tag `v0.1` once the prototype works end-to-end.

## Recheck (review of this plan)
- ✅ 301 vs 302: chose 302 — 301 breaks click counting and makes link edits impossible.
- ✅ Alias race: two requests for the same alias → rely on DB unique constraint, not a pre-check alone.
- ✅ Cache invalidation: links are immutable in v0.1; expiry is checked on cached entries too (store `expires_at` in cache).
- ✅ Open-redirect/loop abuse: own-domain check + scheme whitelist.
- ✅ Tests must not need Postgres/Redis → SQLite + LRU fallback is exercised by tests; the same code path is used in prod with env vars.
- ✅ Routing conflict between SPA and short codes: nginx sends `/` and `/assets/*` to the SPA, everything matching the code pattern to the API.
- ⚠️ Actual hosting needs your account (VPS/Fly/Render, or Vercel for the frontend). Compose works on any Docker host; added to "next steps".
