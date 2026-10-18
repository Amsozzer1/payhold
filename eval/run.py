"""make eval: runs the report seeds through both deciders and writes every result file.

python -m eval.run --seeds 1 2 3 4 5 --n 500
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
from pathlib import Path

from eval import gate, report, web_export
from eval.runner import decision_record, run_seed
from generator import settings
from generator.__main__ import generate
from generator.heldout import LABELS as HELDOUT_LABELS
from generator.heldout import generate_heldout
from generator.validate_heldout import validate
from payhold.extract.pdf import extract_packet

# A held-out packet may only be held for a reason its own feature could cause. Anything else means
# the generator collided with main-stream state, and the run fails rather than reporting it.
HELDOUT_ALLOWED = {
    "dba_on_bol": {"payhold": {"double_brokering"}, "baseline": set()},
    "same_load_no_other_broker": {
        "payhold": {"duplicate_rebill", "double_factoring"},
        "baseline": {"baseline_duplicate_load"},
    },
}

DROP_FIRST = 100  # warm-up packets dropped once, at the start of the process


def seed_dir(seed: int, data: Path) -> Path:
    return data / f"seed-{seed}"


def ensure_generated(seed: int, n: int, data: Path) -> Path:
    d = seed_dir(seed, data)
    if not (d / "truth.json").exists():
        generate(seed, n, d)
    return d


def nearest_rank(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def machine() -> str:
    def sysctl(k: str) -> str:
        r = subprocess.run(["sysctl", "-n", k], capture_output=True, text=True)
        return r.stdout.strip() or "unknown"

    if platform.system() == "Darwin":
        return f"{sysctl('hw.model')}, {sysctl('machdep.cpu.brand_string')}, macOS {platform.mac_ver()[0]}"
    return f"{platform.machine()}, {platform.platform()}"


def write_latency(timings: list[dict], results: Path) -> str:
    kept = timings[DROP_FIRST:]
    (results / "latency_raw.json").write_text(json.dumps({"dropped_first": DROP_FIRST, "packets": timings}, indent=0) + "\n")
    stages = {
        "extraction (3 PDFs)": [t["extract_ms"] for t in kept],
        "checks": [t["checks_ms"] for t in kept],
        "extraction + checks": [t["extract_ms"] + t["checks_ms"] for t in kept],
    }
    lines = [
        "# Decision latency",
        "",
        f"In-process, sequential, one Python process over the main-stream eval packets of seeds {sorted({t['seed'] for t in timings})}. "
        f"The first {DROP_FIRST} packets were dropped once as warm-up. Held-out packets are excluded. "
        "Checks run against the in-memory store. Single run.",
        "",
        f"- Machine: {machine()}",
        f"- Python {platform.python_version()}",
        f"- n = {len(kept)} packets",
        "",
        "| Stage | p50 (ms) | p95 (ms) | n |",
        "|---|---|---|---|",
    ]
    for name, vals in stages.items():
        lines.append(f"| {name} | {nearest_rank(vals, 0.50):.2f} | {nearest_rank(vals, 0.95):.2f} | {len(vals)} |")
    lines += ["", "Percentiles are nearest-rank. Raw per-packet timings: `results/latency_raw.json`.", ""]
    text = "\n".join(lines)
    (results / "latency.md").write_text(text)
    return text


def run_heldout(run, d: Path) -> list[dict]:
    """Each held-out packet is decided against its own snapshot of both deciders at end of stream."""
    if not (d / "heldout_truth.json").exists():
        generate_heldout(run.seed, d)
    problems = validate(d)
    if problems:
        raise SystemExit("held-out validator failed:\n" + "\n".join(problems[:20]))
    truth = {p["request_id"]: p for p in json.loads((d / "heldout_truth.json").read_text())["packets"]}
    records = []
    for req in json.loads((d / "heldout_requests.json").read_text()):
        packet = extract_packet(req, d)
        ph, bl = run.payhold.snapshot(), run.baseline.snapshot()
        rec = decision_record(truth[req["request_id"]], bl.process(packet), ph.process(packet))
        # Eval-side probe, not a decider: would a rate-con-name-only comparison have flagged this BOL?
        rec["bol_name_matches_ratecon"] = packet.bol.carrier_name.norm == packet.ratecon.carrier_name.norm
        allowed = HELDOUT_ALLOWED[rec["lookalike"]]
        for who in ("payhold", "baseline"):
            stray = set(rec[who]["codes"]) - allowed[who]
            if stray:
                raise SystemExit(f"held-out collision: {req['request_id']} ({rec['lookalike']}) held by {who} for {sorted(stray)}")
        records.append(rec)
    return records


def evaluate(seeds: list[int], n: int, data: Path, results: Path, web: Path | None, freeze: str | None, heldout: bool = False) -> dict:
    results.mkdir(parents=True, exist_ok=True)
    decisions: dict = {"synthetic": True, "seeds": seeds, "main": {}}
    held: dict = {"synthetic": True, "seeds": seeds, "labels": HELDOUT_LABELS, "heldout": {}}
    timings: list[dict] = []
    first = None
    for s in seeds:
        d = ensure_generated(s, n, data)
        run = run_seed(d)
        first = first or (run, d)
        decisions["main"][str(s)] = [decision_record(r.truth, r.baseline, r.payhold) for r in run.rows]
        timings += [
            {"seed": s, "request_id": r.request_id, "extract_ms": round(r.extract_s * 1000, 3), "checks_ms": round(r.checks_s * 1000, 3)}
            for r in run.rows
        ]
        print(f"seed {s}: {len(run.rows)} packets decided")
        if heldout:
            held["heldout"][str(s)] = run_heldout(run, d)
            print(f"seed {s}: {len(held['heldout'][str(s)])} held-out packets decided against the end-of-stream snapshot")
    (results / "decisions.json").write_text(json.dumps(decisions, indent=1, sort_keys=True) + "\n")
    if heldout:
        (results / "heldout_decisions.json").write_text(json.dumps(held, indent=1, sort_keys=True) + "\n")
    print(write_latency(timings, results))
    print(report.write(results, freeze))
    if web is not None:
        exported = web_export.export(first[0], first[1], web)
        print(f"web data: {web} (featured {exported['featured']['request_id']})")
    return decisions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=settings.REPORT_SEEDS)
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--results", type=Path, default=Path("results"))
    ap.add_argument("--web", type=Path, default=Path("web/public/data"))
    args = ap.parse_args()
    report_run = bool(set(args.seeds) & set(settings.REPORT_SEEDS))
    freeze = gate.check() if report_run else None
    evaluate(args.seeds, args.n, args.data, args.results, args.web, freeze, heldout=report_run)


if __name__ == "__main__":
    main()
