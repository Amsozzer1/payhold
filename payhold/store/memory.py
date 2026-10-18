"""In-memory store with the same interface and a lock. The eval uses this one."""

from __future__ import annotations

import copy
import threading
from dataclasses import replace

from payhold.store.base import PayoutItem, Seen


class MemoryStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._seen: dict[str, dict[str, Seen]] = {}
        self._paid: dict[str, PayoutItem] = {}
        self._audit: dict[str, list[dict]] = {}
        self._audit_seq = 0

    def put_seen(self, item: Seen) -> None:
        with self._lock:
            self._seen.setdefault(item.pk, {})[item.sk] = item

    def seen(self, pk: str) -> list[Seen]:
        with self._lock:
            return sorted(self._seen.get(pk, {}).values(), key=lambda s: (s.at, s.request_id))

    def set_status(self, pk: str, factor_id: str, request_id: str, status: str) -> None:
        with self._lock:
            sk = f"{factor_id}#{request_id}"
            self._seen[pk][sk] = replace(self._seen[pk][sk], status=status)

    def claim_payout(self, pk: str, request_id: str, token: str, lease_until: str, now: str) -> bool:
        """attribute_not_exists(pk) OR (request_id = :rid AND #s = :pending AND lease_until < :now)."""
        with self._lock:
            cur = self._paid.get(pk)
            if cur is None or (cur.request_id == request_id and cur.status == "pending" and cur.lease_until < now):
                self._paid[pk] = PayoutItem(pk, request_id, token, "pending", lease_until)
                return True
            return False

    def mark_sent(self, pk: str, token: str) -> bool:
        with self._lock:
            cur = self._paid.get(pk)
            if cur is None or cur.attempt_token != token:
                return False
            self._paid[pk] = replace(cur, status="sent")
            return True

    def get_payout(self, pk: str) -> PayoutItem | None:
        with self._lock:
            return self._paid.get(pk)

    def append_audit(self, request_id: str, ts: str, record: dict) -> None:
        with self._lock:
            self._audit_seq += 1
            self._audit.setdefault(request_id, []).append({"sk": f"{ts}#{self._audit_seq:08d}", **record})

    def audit(self, request_id: str) -> list[dict]:
        with self._lock:
            return list(self._audit.get(request_id, []))

    def snapshot(self) -> "MemoryStore":
        with self._lock:
            s = MemoryStore()
            s._seen = copy.deepcopy(self._seen)
            s._paid = dict(self._paid)
            s._audit = copy.deepcopy(self._audit)
            s._audit_seq = self._audit_seq
            return s
