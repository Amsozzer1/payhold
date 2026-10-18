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
        t1 = time.perf_counter()
        p_dec = ph.process(packet)  # both deciders get this same Packet object
        t2 = time.perf_counter()
        b_dec = bl.process(packet)
        rows.append(Row(req["request_id"], packet, truth[req["request_id"]], b_dec, p_dec, t1 - t0, t2 - t1))
    return SeedRun(world["seed"], world, rows, ph, bl)
