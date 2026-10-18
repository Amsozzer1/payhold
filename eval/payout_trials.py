"""Duplicate-payout trials: rail attempts per load under concurrent and repeated requests.

(a) 50 concurrent distinct request_ids for one load, rail with dedupe=False
(b) 50 concurrent copies of one request_id, rail with dedupe=False
(c) crash after the rail call, clock advanced past the lease, retry: 2 attempts, 1 send (rail dedupes)

python -m eval.payout_trials --store dynamodb --trials 100 --out results/payout_trials.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
import uuid
from collections import Counter
from pathlib import Path

import boto3

from payhold import payout
from payhold.clock import FixedClock, parse
from payhold.rail import FakeRail

CLIENTS = 50
LEASE_SECONDS = 300
START = "2026-03-02T06:00:00Z"


def fresh_key(scenario: str, trial: int) -> str:
    """A unique load_key per trial, so trials never see each other's claims."""
    return hashlib.sha256(f"{scenario}|{trial}|{uuid.uuid4().hex}".encode()).hexdigest() + "#linehaul"


def dynamo_stores(n: int = CLIENTS, prefix: str = "payhold_") -> list:
    """n clients built one after another, each from its own boto3 session."""
    from payhold.store.dynamo import DynamoStore, client

    stores = [DynamoStore(client(session=boto3.session.Session()), prefix) for _ in range(n)]
    stores[0].create_tables()
    return stores


def memory_stores(n: int = CLIENTS) -> list:
    from payhold.store.memory import MemoryStore

    shared = MemoryStore()
    return [shared] * n


def concurrent_trial(stores: list, scenario: str, trial: int) -> dict:
    rail = FakeRail(dedupe=False)
    clock = FixedClock(parse(START))
    key = fresh_key(scenario, trial)
    barrier = threading.Barrier(len(stores))
    results: list[str | None] = [None] * len(stores)
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        rid = f"T{trial}-R{i:02d}" if scenario == "a" else f"T{trial}-R00"
        try:
            barrier.wait()
            results[i] = payout.pay(stores[i], rail, clock, rid, key, 100_000, LEASE_SECONDS)
        except BaseException as e:  # surfaced below; a thread must never swallow a failure
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(stores))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]
    return {"attempts": rail.attempts_for(key), "results": dict(Counter(results))}


def crash_trial(stores: list, trial: int) -> dict:
    store = stores[0]
    rail = FakeRail(dedupe=True)
    clock = FixedClock(parse(START))
    key = fresh_key("c", trial)
    rid = f"T{trial}-R00"
    try:
        payout.pay(store, rail, clock, rid, key, 100_000, LEASE_SECONDS, crash_after_send=True)
        raise AssertionError("crash hook did not fire")
    except payout.Crash:
        pass
    during_lease = payout.pay(store, rail, clock, rid, key, 100_000, LEASE_SECONDS)
    clock.advance(LEASE_SECONDS + 1)
    after_lease = payout.pay(store, rail, clock, rid, key, 100_000, LEASE_SECONDS)
    return {
        "attempts": rail.attempts_for(key),
        "sends": rail.sends_for(key),
        "retry_during_lease": during_lease,
        "retry_after_lease": after_lease,
        "final_status": store.get_payout(key).status,
    }


def run(stores: list, trials: int) -> dict:
    out = {}
    for scenario in ("a", "b"):
        rows = [concurrent_trial(stores, scenario, t) for t in range(trials)]
        totals: Counter = Counter()
        for r in rows:
            totals.update(r["results"])
        attempts = [r["attempts"] for r in rows]
        out[scenario] = {
            "trials": trials,
            "clients": len(stores),
            "attempts_min": min(attempts),
            "attempts_max": max(attempts),
            "results_total": dict(sorted(totals.items())),
            "attempts_per_trial": attempts,
        }
    rows = [crash_trial(stores, t) for t in range(trials)]
    out["c"] = {
        "trials": trials,
        "attempts_per_trial": [r["attempts"] for r in rows],
        "sends_per_trial": [r["sends"] for r in rows],
        "retry_during_lease": dict(Counter(r["retry_during_lease"] for r in rows)),
        "retry_after_lease": dict(Counter(r["retry_after_lease"] for r in rows)),
        "final_status": dict(Counter(r["final_status"] for r in rows)),
    }
    return out


def naive_claim(self, pk, request_id, token, lease_until, now):
    """Control only, never used by payhold: read, then write without a condition."""
    if self.get_payout(pk) is not None:
        return False
    self.ddb.put_item(
        TableName=self.paid,
        Item={"pk": {"S": pk}, "request_id": {"S": request_id}, "attempt_token": {"S": token},
              "status": {"S": "pending"}, "lease_until": {"S": lease_until}},
    )
    return True


def control(trials: int) -> dict:
    """Scenario (a) with the conditional write swapped for read-then-write, to show what it prevents."""
    from payhold.store.dynamo import DynamoStore

    stores = dynamo_stores()
    for s in stores:
        s.claim_payout = naive_claim.__get__(s, DynamoStore)
    attempts = [concurrent_trial(stores, "a", t)["attempts"] for t in range(trials)]
    return {"control": "read-then-write claim, scenario (a)", "trials": trials, "clients": len(stores),
            "attempts_min": min(attempts), "attempts_max": max(attempts), "attempts_per_trial": attempts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", choices=["dynamodb", "memory"], default="dynamodb")
    ap.add_argument("--trials", type=int, default=100)
    ap.add_argument("--control", action="store_true", help="run the read-then-write control instead")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.control:
        result = control(args.trials)
        if args.out:
            args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
        print(f"control: {result['trials']} trials x {result['clients']} clients, rail attempts per load min {result['attempts_min']} max {result['attempts_max']}")
        return
    stores = dynamo_stores() if args.store == "dynamodb" else memory_stores()
    result = {"store": args.store, "image": "amazon/dynamodb-local:3.3.1" if args.store == "dynamodb" else None, **run(stores, args.trials)}
    text = json.dumps(result, indent=1, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n")
    for s in ("a", "b"):
        r = result[s]
        print(f"({s}) {r['trials']} trials x {r['clients']} clients: rail attempts per load min {r['attempts_min']} max {r['attempts_max']}; {r['results_total']}")
    c = result["c"]
    print(f"(c) {c['trials']} trials: attempts {sorted(set(c['attempts_per_trial']))}, sends {sorted(set(c['sends_per_trial']))}, during lease {c['retry_during_lease']}, after lease {c['retry_after_lease']}")


if __name__ == "__main__":
    main()
