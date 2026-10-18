import filecmp
import json
from pathlib import Path

import pytest

from generator import settings
from generator.__main__ import expected_counts, generate


def tree_identical(a: Path, b: Path) -> bool:
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    match, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(tree_identical(a / d, b / d) for d in cmp.common_dirs)


def test_counts_match_config_exactly(seed1):
    truth = json.loads((seed1 / "truth.json").read_text())
    assert truth["counts"] == expected_counts(500)
    assert sum(1 for _ in (seed1 / "pdfs").rglob("*.pdf")) == 1500


def test_rerun_is_byte_identical(seed1, tmp_path):
    generate(1, 500, tmp_path / "again")
    assert tree_identical(seed1, tmp_path / "again")


def test_followers_come_after_their_anchor_through_another_factor(seed1):
    packets = json.loads((seed1 / "truth.json").read_text())["packets"]
    by_id = {p["request_id"]: p for p in packets}
    followers = [p for p in packets if p["issue_type"] == 3]
    assert followers
    for f in followers:
        a = by_id[f["anchor_request_id"]]
        assert a["seq"] < f["seq"]
        assert a["factor_id"] != f["factor_id"]
        assert a["issue_type"] == 0 and a["lookalike"] is None
        assert a["docs"] == f["docs"]


def test_world_is_synthetic(seed1):
    world = json.loads((seed1 / "world.json").read_text())
    carriers = world["carriers"]
    assert sum(1 for c in carriers if c["dba"]) >= 0.2 * len(carriers)
    for c in carriers + world["brokers"]:
        assert c["usdot"].startswith("99")
    for c in carriers:
        for r in c["remit_history"]:
            assert r["routing"].startswith("000")


def test_bols_print_legal_name_only(seed1):
    world = json.loads((seed1 / "world.json").read_text())
    dbas = {c["dba"] for c in world["carriers"] if c["dba"]}
    packets = json.loads((seed1 / "truth.json").read_text())["packets"]
    for p in packets:
        assert p["docs"]["bol"]["carrier_name"] not in dbas
        assert p["docs"]["invoice"]["carrier_name"] not in dbas


def test_rates_leave_room_for_clean_packets():
    bad = sum(settings.ISSUE_RATES.values())
    look = sum(settings.LOOKALIKE_RATES.values())
    # seen look-alikes are about 15% of main-stream clean packets
    assert 0.12 < look / (1 - bad) < 0.18
