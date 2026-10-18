import filecmp

from eval.run import evaluate


def test_two_runs_of_one_seed_are_byte_identical(tmp_path):
    outs = []
    for run in ("one", "two"):
        base = tmp_path / run
        evaluate([7], 120, base / "data", base / "results", None, None)
        outs.append(base)
    a, b = outs
    for rel in ("data/seed-7/truth.json", "data/seed-7/requests.json", "data/seed-7/world.json", "results/decisions.json", "results/numbers.md"):
        assert filecmp.cmp(a / rel, b / rel, shallow=False), rel
    pdfs = sorted(p.relative_to(a) for p in (a / "data/seed-7/pdfs").rglob("*.pdf"))
    assert len(pdfs) == 360
    for rel in pdfs:
        assert filecmp.cmp(a / rel, b / rel, shallow=False), rel
