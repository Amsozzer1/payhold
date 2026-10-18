"""python -m generator gen --seed 1 --n 500 [--out data/seed-1]"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from generator import settings
from generator.build import Packet, build, iso
from generator.render import render_packet


def dump(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")


def request_record(p: Packet) -> dict:
    """What a factor submits: no labels."""
    base = f"pdfs/{p.request_id}"
    return {
        "request_id": p.request_id,
        "factor_id": p.factor_id,
        "requested_at": iso(p.requested_at),
        "docs": {k: f"{base}/{k}.pdf" for k in ("ratecon", "bol", "invoice")},
    }


def truth_record(p: Packet) -> dict:
    return {
        "request_id": p.request_id,
        "seq": p.seq,
        "factor_id": p.factor_id,
        "issue_type": p.issue_type,
        "issue_name": settings.ISSUE_NAMES[p.issue_type],
        "exposure_cents": p.exposure_cents,
        "lookalike": p.lookalike,
        "anchor_request_id": p.anchor_request_id,
        "docs": {"ratecon": p.docs.ratecon, "bol": p.docs.bol, "invoice": p.docs.invoice},
    }


def counts(packets: list[Packet]) -> dict:
    c: dict[str, int] = {}
    for p in packets:
        key = settings.ISSUE_NAMES[p.issue_type] if p.issue_type else (p.lookalike or "plain")
        c[key] = c.get(key, 0) + 1
    return c


def expected_counts(n: int) -> dict:
    c = {settings.ISSUE_NAMES[t]: round(n * r) for t, r in settings.ISSUE_RATES.items()}
    c.update({k: round(n * r) for k, r in settings.LOOKALIKE_RATES.items()})
    c["plain"] = n - sum(c.values())
    return c


def generate(seed: int, n: int, out: Path) -> dict:
    world, packets = build(seed, n)
    out.mkdir(parents=True, exist_ok=True)
    for p in packets:
        render_packet(p.docs, out / "pdfs" / p.request_id)
    dump(world.to_json(), out / "world.json")
    dump([request_record(p) for p in packets], out / "requests.json")
    got = counts(packets)
    truth = {
        "synthetic": True,
        "seed": seed,
        "n": n,
        "counts": got,
        "packets": [truth_record(p) for p in packets],
    }
    dump(truth, out / "truth.json")
    want = expected_counts(n)
    if got != want:
        raise SystemExit(f"planted counts {got} != configured {want}")
    return got


def main() -> None:
    ap = argparse.ArgumentParser(prog="generator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="main stream")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--n", type=int, default=500)
    g.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.cmd == "gen":
        out = args.out or Path("data") / f"seed-{args.seed}"
        got = generate(args.seed, args.n, out)
        pdfs = sum(1 for _ in (out / "pdfs").rglob("*.pdf"))
        print(f"seed {args.seed}: {args.n} packets, {pdfs} PDFs in {out}")
        print("planted counts (match config):", json.dumps(got, sort_keys=True))


if __name__ == "__main__":
    main()
