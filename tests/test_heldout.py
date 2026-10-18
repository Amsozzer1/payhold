import json

from eval.run import evaluate
from generator.validate_heldout import validate


def test_heldout_leaves_main_stream_decisions_byte_identical(tmp_path):
    data = tmp_path / "data"
    evaluate([7], 120, data, tmp_path / "without", None, None, heldout=False)
    evaluate([7], 120, data, tmp_path / "with", None, None, heldout=True)
    assert (tmp_path / "without/decisions.json").read_bytes() == (tmp_path / "with/decisions.json").read_bytes()
    assert not (tmp_path / "without/heldout_decisions.json").exists()

    held = json.loads((tmp_path / "with/heldout_decisions.json").read_text())["heldout"]["7"]
    assert len(held) == 50
    assert sorted({r["lookalike"] for r in held}) == ["dba_on_bol", "same_load_no_other_broker"]
    assert validate(data / "seed-7") == []
