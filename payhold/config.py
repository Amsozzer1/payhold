"""Thresholds from config/thresholds.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "thresholds.toml"


@dataclass(frozen=True)
class Thresholds:
    padding_tolerance_cents: int
    remit_recent_change_days: int
    payout_lease_seconds: int


def load(path: Path = DEFAULT_PATH) -> Thresholds:
    t = tomllib.loads(path.read_text())
    return Thresholds(
        padding_tolerance_cents=t["padding"]["tolerance_cents"],
        remit_recent_change_days=t["remit"]["recent_change_days"],
        payout_lease_seconds=t["payout"]["lease_seconds"],
    )
