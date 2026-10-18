"""A fake payment rail. It logs every attempt and, like real rails, dedupes on the idempotency key."""

from __future__ import annotations

import threading


class FakeRail:
    def __init__(self, dedupe: bool = True):
        self.dedupe = dedupe  # dedupe=False is test-only: it proves the store alone holds the line
        self.attempts: list[dict] = []
        self.sent: dict[str, dict] = {}
        self._lock = threading.Lock()

    def send(self, key: str, amount_cents: int, request_id: str) -> str:
        with self._lock:
            self.attempts.append({"key": key, "amount_cents": amount_cents, "request_id": request_id})
            if self.dedupe and key in self.sent:
                return "deduped"
            self.sent.setdefault(key, {"amount_cents": amount_cents, "request_id": request_id, "count": 0})
            self.sent[key]["count"] += 1
            return "sent"

    def attempts_for(self, key: str) -> int:
        return sum(1 for a in self.attempts if a["key"] == key)

    def sends_for(self, key: str) -> int:
        return self.sent.get(key, {}).get("count", 0)
