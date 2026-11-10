# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Test de charge d'un service Cloud Run authentifié : K clients en boucle fermée, p50/p99, débit, erreurs.

uv run tools/loadtest.py --url https://... --clients 8 --duration 60
uv run tools/loadtest.py --url https://... --cold
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import httpx

SEED = 20261110


def identity_token() -> str:
    if token := os.environ.get("ID_TOKEN"):
        return token
    return subprocess.run(
        ["gcloud", "auth", "print-identity-token"], check=True, capture_output=True, text=True
    ).stdout.strip()


def body(rng: random.Random) -> bytes:
    tx = {
        "transaction_id": rng.randrange(10**9),
        "client_id": rng.randrange(1, 5000),
        "timestamp": "2025-07-01T12:00:00Z",
        "amount": round(rng.uniform(1, 500), 2),
        "merchant_category": rng.randrange(20),
        "channel": rng.randrange(3),
        "country_match": rng.random() < 0.9,
    }
    return json.dumps({"transactions": [tx]}).encode()


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


async def client(
    http: httpx.AsyncClient, url: str, deadline: float, rng: random.Random, rows: list
):
    while perf_counter() < deadline:
        start = perf_counter()
        try:
            status = (await http.post(url + "/score", content=body(rng))).status_code
        except httpx.HTTPError:
            status = 0
        rows.append((datetime.now(UTC).isoformat(), status, (perf_counter() - start) * 1000))


async def load(url: str, headers: dict, clients: int, duration: float) -> list:
    rows: list = []
    limits = httpx.Limits(max_connections=clients)
    async with httpx.AsyncClient(headers=headers, timeout=60, limits=limits) as http:
        deadline = perf_counter() + duration
        await asyncio.gather(
            *(client(http, url, deadline, random.Random(SEED + i), rows) for i in range(clients))
        )
    return rows


def cold(url: str, headers: dict, warm: int) -> None:
    rng = random.Random(SEED)
    with httpx.Client(headers=headers, timeout=120) as http:
        timings = []
        for _ in range(1 + warm):
            start = perf_counter()
            http.post(url + "/score", content=body(rng)).raise_for_status()
            timings.append((perf_counter() - start) * 1000)
    print(f"première demande : {timings[0]:.0f} ms")
    print(f"demandes suivantes (médiane de {warm}) : {percentile(timings[1:], 0.5):.0f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--clients", type=int, default=8)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--cold", action="store_true", help="chronomètre la première demande")
    parser.add_argument("--out", type=Path, default=Path("loadtest.csv"))
    args = parser.parse_args()

    url = args.url.rstrip("/")
    headers = {"Authorization": f"Bearer {identity_token()}", "Content-Type": "application/json"}
    if args.cold:
        return cold(url, headers, warm=10)

    rows = asyncio.run(load(url, headers, args.clients, args.duration))
    with args.out.open("w", newline="") as f:
        csv.writer(f).writerows([("time", "status", "latency_ms"), *rows])

    ok = [ms for _, status, ms in rows if status == 200]
    print(f"clients={args.clients} durée={args.duration:.0f}s demandes={len(rows)}")
    print(f"débit : {len(rows) / args.duration:.1f} demandes/s, erreurs : {len(rows) - len(ok)}")
    if ok:
        print(f"p50 : {percentile(ok, 0.5):.0f} ms, p99 : {percentile(ok, 0.99):.0f} ms")
    print(f"latences unitaires : {args.out}")


if __name__ == "__main__":
    main()
