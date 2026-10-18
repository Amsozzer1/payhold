"""Runs one seed's main stream through the baseline and payhold, one packet at a time in arrival order."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from payhold.baseline import Baseline
from payhold.decision import Decision
from payhold.engine import Payhold
from payhold.extract.pdf import extract_packet
from payhold.models import Packet


@dataclass
class Row:
    request_id: str
    packet: Packet
    truth: dict
    baseline: Decision
    payhold: Decision
    extract_s: float
    checks_s: float


@dataclass
class SeedRun:
    seed: int
    world: dict
    rows: list[Row]
    payhold: Payhold
    baseline: Baseline


def load_seed(seed_dir: Path) -> tuple[dict, list[dict], dict]:
    world = json.loads((seed_dir / "world.json").read_text())
    requests = json.loads((seed_dir / "requests.json").read_text())
    truth = {p["request_id"]: p for p in json.loads((seed_dir / "truth.json").read_text())["packets"]}
    return world, requests, truth


def run_seed(seed_dir: Path, deciders=None) -> SeedRun:
    world, requests, truth = load_seed(seed_dir)
    ph = Payhold.from_world(world)
    bl = Baseline(world)
    if deciders:
        deciders(ph, bl)
    rows = []
    for req in requests:
        t0 = time.perf_counter()
        packet = extract_packet(req, seed_dir)
        extract_s = time.perf_counter() - t0
        timings: dict = {}
        p_dec = ph.process(packet, timings)
        b_dec = bl.process(packet)  # the same Packet object payhold just read
        rows.append(Row(req["request_id"], packet, truth[req["request_id"]], b_dec, p_dec, extract_s, timings.get("checks", 0.0)))
    return SeedRun(world["seed"], world, rows, ph, bl)


def decision_record(truth: dict, baseline: Decision, payhold: Decision) -> dict:
    return {
        "request_id": truth["request_id"],
        "seq": truth["seq"],
        "factor_id": truth["factor_id"],
        "issue_type": truth["issue_type"],
        "issue_name": truth["issue_name"],
        "lookalike": truth["lookalike"],
        "exposure_cents": truth["exposure_cents"],
        "baseline": {"decision": baseline.decision, "codes": [r.code for r in baseline.reasons]},
        "payhold": {
            "decision": payhold.decision,
            "codes": [r.code for r in payhold.reasons],
            "messages": [r.message for r in payhold.reasons],
        },
    }
