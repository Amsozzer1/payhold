import json

import pytest

from eval.runner import run_seed
from payhold.engine import Payhold
from payhold.handlers import decide, ingest, pay, runtime


@pytest.fixture(scope="session")
def seed1_run(seed1):
    seen = {"payhold": [], "baseline": []}

    def spy(ph, bl):
        for name, d in (("payhold", ph), ("baseline", bl)):
            orig = d.process

            def wrapped(packet, *args, _orig=orig, _name=name):
                seen[_name].append(packet)
                return _orig(packet, *args)

            d.process = wrapped

    run = run_seed(seed1, spy)
    return run, seen


def test_baseline_and_payhold_receive_identical_packets(seed1_run):
    run, seen = seed1_run
    assert len(seen["payhold"]) == len(seen["baseline"]) == 500
    assert all(a is b for a, b in zip(seen["payhold"], seen["baseline"]))


def test_who_catches_what_seed1(seed1_run):
    run, _ = seed1_run
    for row in run.rows:
        t = row.truth
        if t["issue_type"] in (1, 2):
            assert row.baseline.decision == "hold" and row.payhold.decision == "hold"
        elif t["issue_type"] in (3, 4, 5):
            assert row.baseline.decision == "pay" and row.payhold.decision == "hold"


def test_every_decision_is_in_the_audit_log(seed1_run):
    run, _ = seed1_run
    for row in run.rows[:50]:
        log = run.payhold.store.audit(row.request_id)
        assert [e["decision"] for e in log] == [row.payhold.decision]


def test_handlers_match_in_process_pipeline(seed1):
    world = json.loads((seed1 / "world.json").read_text())
    requests = json.loads((seed1 / "requests.json").read_text())[:40]
    direct = Payhold.from_world(world)
    runtime.set(Payhold.from_world(world))
    try:
        for req in requests:
            out = ingest.handler({"request": req, "base_dir": str(seed1)})
            out = decide.handler(out)
            if out["decision"]["decision"] == "pay":
                out = pay.handler(out)
            from payhold.extract.pdf import extract_packet

            want = direct.process(extract_packet(req, seed1))
            assert out["decision"]["decision"] == want.decision
            assert [r["code"] for r in out["decision"]["reasons"]] == [r.code for r in want.reasons]
    finally:
        runtime.set(None)
