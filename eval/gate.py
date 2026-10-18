"""Report seeds only run on a clean tree whose decision code matches the freeze commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

TRACKED_SOURCE = ["payhold/", "config/", "generator/", "eval/", "pyproject.toml", "uv.lock"]
FROZEN = ["payhold/", "config/", "pyproject.toml", "uv.lock"]
FREEZE_FILE = Path("results/freeze.txt")


class GateError(SystemExit):
    pass


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def check() -> str:
    """Returns the freeze commit. Raises GateError if the tree is dirty or decision code moved."""
    dirty = git("status", "--porcelain", "--", *TRACKED_SOURCE).stdout.strip()
    if dirty:
        raise GateError(f"refusing report seeds: tracked source is dirty:\n{dirty}")
    if not FREEZE_FILE.exists():
        raise GateError(f"refusing report seeds: {FREEZE_FILE} is missing")
    freeze = FREEZE_FILE.read_text().split()[0]
    if git("diff", "--quiet", freeze, "HEAD", "--", *FROZEN).returncode != 0:
        raise GateError(f"refusing report seeds: {' '.join(FROZEN)} differ from freeze commit {freeze}")
    return freeze
