"""Who catches what, by issue type and look-alike kind. Used on dev seeds to check the design.

python -m eval.whocatches data/seed-101 data/seed-102
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from eval.runner import run_seed


def category(truth: dict) -> str:
    if truth["issue_type"]:
        return f"{truth['issue_type']} {truth['issue_name']}"
    return f"clean: {truth['lookalike'] or 'plain'}"


def table(seed_dirs: list[Path]) -> str:
    held = {"baseline": Counter(), "payhold": Counter()}
    total = Counter()
    for d in seed_dirs:
        for row in run_seed(d).rows:
            c = category(row.truth)
            total[c] += 1
            held["baseline"][c] += row.baseline.decision == "hold"
            held["payhold"][c] += row.payhold.decision == "hold"
    lines = ["| Category | n | Baseline held | payhold held |", "|---|---|---|---|"]
    for c in sorted(total):
        lines.append(f"| {c} | {total[c]} | {held['baseline'][c]} | {held['payhold'][c]} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(table([Path(a) for a in sys.argv[1:]]))
