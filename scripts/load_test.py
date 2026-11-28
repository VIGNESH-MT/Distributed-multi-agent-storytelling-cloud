"""Concurrency and throughput experiments against a deployed storytelling API.

Modes
-----
conflict
    N clients submit an agentic revision against the same story version at
    the same moment. With version-checked commits exactly one should commit
    and the others should receive HTTP 409.

throughput
    N clients each create their own story and keep requesting agentic
    revisions for a fixed duration. Reports committed revisions per second
    and latency percentiles. Combine with AGENT_PROVIDER=mock and
    MOCK_AGENT_CPU_MS > 0 to generate load that triggers autoscaling.

Examples
--------
    python scripts/load_test.py --base-url http://34.1.2.3 conflict --clients 5
    python scripts/load_test.py --base-url http://34.1.2.3 throughput \
        --clients 20 --duration 300 --output experiments/throughput-20.json
"""

import argparse
import json
import statistics
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

USER_REQUEST = (
    "Continue the story with one meaningful development while preserving "
    "the established characters and their motivations."
)

OPENING = (
    "Mira, an apprentice lighthouse keeper, notices a signal from an "
    "abandoned island. Her mentor Elias warns her never to answer it."
)


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round(pct / 100 * (len(ordered) - 1))
    return ordered[index]


def summarise(samples: list[dict], elapsed_s: float) -> dict:
    latencies = [s["latency_ms"] for s in samples]
    outcomes = Counter(s["outcome"] for s in samples)
    committed = outcomes.get("committed", 0)

    return {
        "requests": len(samples),
        "outcomes": dict(outcomes),
        "elapsed_s": round(elapsed_s, 2),
        "committed_per_s": round(committed / elapsed_s, 3) if elapsed_s else None,
        "latency_ms": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "max": max(latencies) if latencies else None,
            "mean": round(statistics.fmean(latencies), 1) if latencies else None,
        },
    }


def create_story(client: httpx.Client, title: str) -> dict:
    response = client.post(
        "/stories",
        json={"title": title, "initial_content": OPENING},
    )
    response.raise_for_status()
    return response.json()


def request_revision(client: httpx.Client, story_id: str, version: int) -> dict:
    started = time.perf_counter()

    try:
        response = client.post(
            f"/stories/{story_id}/agentic-revisions",
            json={"expected_version": version, "user_request": USER_REQUEST},
        )
    except httpx.HTTPError as exc:
        return {
            "outcome": f"error:{type(exc).__name__}",
            "latency_ms": (time.perf_counter() - started) * 1000,
            "finished_at": time.time(),
        }

    latency_ms = (time.perf_counter() - started) * 1000
    sample = {
        "status_code": response.status_code,
        "latency_ms": latency_ms,
        "finished_at": time.time(),
    }

    if response.status_code == 200:
        body = response.json()
        sample["outcome"] = body["status"]
        sample["committed_version"] = body.get("committed_version")
    elif response.status_code == 409:
        sample["outcome"] = "conflict"
    else:
        sample["outcome"] = f"http_{response.status_code}"

    return sample


def run_conflict(base_url: str, clients: int, timeout: float) -> dict:
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        story = create_story(client, "Concurrency experiment")

    barrier = threading.Barrier(clients)

    def attempt(_: int) -> dict:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            barrier.wait()
            return request_revision(client, story["id"], story["version"])

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=clients) as pool:
        samples = list(pool.map(attempt, range(clients)))
    elapsed = time.perf_counter() - started

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        final = client.get(f"/stories/{story['id']}").json()

    summary = summarise(samples, elapsed)
    summary["story_id"] = story["id"]
    summary["base_version"] = story["version"]
    summary["final_version"] = final["version"]
    summary["consistent"] = (
        summary["outcomes"].get("committed", 0) <= 1
        and final["version"] == story["version"] + summary["outcomes"].get("committed", 0)
    )
    return {"summary": summary, "samples": samples}


def run_throughput(base_url: str, clients: int, duration: float, timeout: float) -> dict:
    deadline = time.perf_counter() + duration
    samples: list[dict] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            story = create_story(client, f"Throughput experiment {index}")
            version = story["version"]

            while time.perf_counter() < deadline:
                sample = request_revision(client, story["id"], version)
                sample["client"] = index

                with lock:
                    samples.append(sample)

                if sample.get("committed_version"):
                    version = sample["committed_version"]
                elif sample["outcome"] == "conflict":
                    version = client.get(f"/stories/{story['id']}").json()["version"]

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=clients) as pool:
        list(pool.map(worker, range(clients)))
    elapsed = time.perf_counter() - started

    return {"summary": summarise(samples, elapsed), "samples": samples}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True, help="e.g. http://34.1.2.3")
    parser.add_argument("--timeout", type=float, default=900, help="per-request timeout in seconds")
    parser.add_argument("--output", type=Path, help="write summary and raw samples as JSON")

    modes = parser.add_subparsers(dest="mode", required=True)

    conflict = modes.add_parser("conflict")
    conflict.add_argument("--clients", type=int, default=5)

    throughput = modes.add_parser("throughput")
    throughput.add_argument("--clients", type=int, default=10)
    throughput.add_argument("--duration", type=float, default=120, help="seconds")

    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    started_utc = datetime.now(timezone.utc).isoformat()

    if args.mode == "conflict":
        result = run_conflict(base_url, args.clients, args.timeout)
    else:
        result = run_throughput(base_url, args.clients, args.duration, args.timeout)

    result["experiment"] = {
        "mode": args.mode,
        "base_url": base_url,
        "clients": args.clients,
        "duration_s": getattr(args, "duration", None),
        "started_utc": started_utc,
    }

    print(json.dumps({"experiment": result["experiment"], "summary": result["summary"]}, indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
