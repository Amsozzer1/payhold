"""Store interface. Two implementations: in-memory (eval) and DynamoDB Local (payout tests)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


def invoice_key(carrier_usdot, invoice_no) -> str:
    return f"inv#{carrier_usdot}#{invoice_no}"


@dataclass(frozen=True)
class Seen:
    """One request seen for a key (a load_key or an invoice key)."""

    pk: str
    factor_id: str
    request_id: str
    status: str  # requested | held | paid | rejected
    at: str
    label: str  # human-readable id for messages, e.g. the load number

    @property
    def sk(self) -> str:
        return f"{self.factor_id}#{self.request_id}"


@dataclass(frozen=True)
class PayoutItem:
    pk: str
    request_id: str
    attempt_token: str
    status: str  # pending | sent
    lease_until: str


class Store(Protocol):
    def put_seen(self, item: Seen) -> None: ...
    def seen(self, pk: str) -> list[Seen]: ...
    def set_status(self, pk: str, factor_id: str, request_id: str, status: str) -> None: ...
    def claim_payout(self, pk: str, request_id: str, token: str, lease_until: str, now: str) -> bool: ...
    def mark_sent(self, pk: str, token: str) -> bool: ...
    def get_payout(self, pk: str) -> PayoutItem | None: ...
    def append_audit(self, request_id: str, ts: str, record: dict) -> None: ...
    def audit(self, request_id: str) -> list[dict]: ...
