"""Pure functions from decision records to the numbers in numbers.md."""

from __future__ import annotations

from statistics import median

ISSUE_TYPES = {1: "padding", 2: "duplicate_rebill", 3: "double_factoring", 4: "bank_change", 5: "double_brokering"}


def exposure_paid(records: list[dict], who: str) -> int:
    return sum(r["exposure_cents"] for r in records if r["issue_type"] and r[who]["decision"] == "pay")


def exposure_planted(records: list[dict]) -> int:
    return sum(r["exposure_cents"] for r in records if r["issue_type"])


def paid_rate(records: list[dict], who: str) -> tuple[int, int]:
    return sum(1 for r in records if r[who]["decision"] == "pay"), len(records)


def plain(records):
    return [r for r in records if not r["issue_type"] and not r["lookalike"]]


def seen(records):
    return [r for r in records if not r["issue_type"] and r["lookalike"]]


def held_by_type(records: list[dict], who: str, t: int) -> tuple[int, int]:
    rs = [r for r in records if r["issue_type"] == t]
    return sum(1 for r in rs if r[who]["decision"] == "hold"), len(rs)


def summary(values: list[float]) -> tuple[float, float, float]:
    return median(values), min(values), max(values)
