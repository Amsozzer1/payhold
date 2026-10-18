"""Injected clocks. Nothing in payhold reads the wall clock directly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def fmt(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FixedClock:
    """A clock that only moves when told to. The eval sets it to each request's synthetic time."""

    def __init__(self, now: datetime):
        self._now = now

    def __call__(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)
