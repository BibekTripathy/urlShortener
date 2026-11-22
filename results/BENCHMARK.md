# Load benchmark

_2026-11-22 20:23 UTC · docker compose on one machine (client shares the CPU) · 8 client processes × 16 connections · 8s per endpoint · clicks recorded for the benchmarked link: 33,210_

| Endpoint | req/s | p50 ms | p95 ms | p99 ms | requests | errors |
|---|---|---|---|---|---|---|
| `GET /healthz` (baseline, no I/O) | 4,893 | 14.2 | 82.6 | 131.5 | 39,143 | 0 |
| `GET /{code}` redirect | 4,145 | 17.0 | 94.6 | 154.2 | 33,160 | 0 |
