"""Carrier registry and remit-to history. In this repo these are fake local tables from world.json."""

from __future__ import annotations

from payhold.clock import parse


class Registry:
    def __init__(self, world: dict):
        self.carriers = {c["usdot"]: c for c in world["carriers"]}
        self.factor_names = {f["id"]: f["name"] for f in world["factors"]}

    def carrier(self, usdot) -> dict | None:
        return self.carriers.get(usdot)

    def factor_name(self, factor_id: str) -> str:
        return self.factor_names.get(factor_id, factor_id)

    @staticmethod
    def remit_at(carrier: dict, at: str) -> dict | None:
        """The remit-to entry in effect at `at`: the latest change at or before it."""
        t = parse(at)
        current = None
        for r in carrier["remit_history"]:
            if parse(r["changed_at"]) <= t and (current is None or parse(r["changed_at"]) >= parse(current["changed_at"])):
                current = r
        return current
