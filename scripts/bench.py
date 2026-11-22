"""Load benchmark against a running stack. Writes results/BENCHMARK.md.

The client runs in several processes so the load generator isn't the bottleneck.
usage: backend/.venv/bin/python scripts/bench.py [base_url] [seconds] [procs] [conns_per_proc]
"""

import asyncio
import multiprocessing as mp
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 10
PROCS = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) // 2)
CONNS = int(sys.argv[4]) if len(sys.argv) > 4 else 16


def run_proc(path: str, expect: int, q) -> None:
    async def main():
        lat, errs = [], 0
        lim = httpx.Limits(max_connections=CONNS, max_keepalive_connections=CONNS)
        async with httpx.AsyncClient(base_url=BASE, limits=lim, timeout=10) as c:
            end = time.perf_counter() + SECS

            async def worker():
                nonlocal errs
                while time.perf_counter() < end:
                    t = time.perf_counter()
                    r = await c.get(path)
                    lat.append((time.perf_counter() - t) * 1000)
                    errs += r.status_code != expect

            await asyncio.gather(*(worker() for _ in range(CONNS)))
        q.put((lat, errs))

    asyncio.run(main())


def bench(path: str, expect: int) -> dict:
    q = mp.Queue()
    ps = [mp.Process(target=run_proc, args=(path, expect, q)) for _ in range(PROCS)]
    for p in ps:
        p.start()
    lat, errs = [], 0
    for _ in ps:
        l_, e = q.get()
        lat += l_
        errs += e
    for p in ps:
        p.join()
    lat.sort()
    pct = lambda p: lat[min(len(lat) - 1, int(len(lat) * p))]  # noqa: E731
    return {"n": len(lat), "rps": len(lat) / SECS, "errs": errs,
            "p50": pct(.5), "p95": pct(.95), "p99": pct(.99)}


if __name__ == "__main__":
    r = httpx.post(f"{BASE}/api/v1/links", json={"url": "https://example.com/bench"})
    r.raise_for_status()
    code = r.json()["code"]
    for _ in range(50):
        httpx.get(f"{BASE}/{code}")

    rows = []
    for label, path, expect in [("`GET /healthz` (baseline, no I/O)", "/healthz", 200),
                                ("`GET /{code}` redirect", f"/{code}", 302)]:
        s = bench(path, expect)
        rows.append(f"| {label} | {s['rps']:,.0f} | {s['p50']:.1f} | {s['p95']:.1f} | "
                    f"{s['p99']:.1f} | {s['n']:,} | {s['errs']} |")
    clicks = httpx.get(f"{BASE}/api/v1/links/{code}").json()["clicks"]

    table = "\n".join([
        "| Endpoint | req/s | p50 ms | p95 ms | p99 ms | requests | errors |",
        "|---|---|---|---|---|---|---|", *rows])
    note = (f"_{datetime.now(UTC):%Y-%m-%d %H:%M UTC} · docker compose on one machine "
            f"(client shares the CPU) · {PROCS} client processes × {CONNS} connections · "
            f"{SECS:.0f}s per endpoint · clicks recorded for the benchmarked link: {clicks:,}_")
    out = Path(__file__).resolve().parent.parent / "results" / "BENCHMARK.md"
    out.write_text(f"# Load benchmark\n\n{note}\n\n{table}\n")
    print(note, table, sep="\n\n")
