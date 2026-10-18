"""At most one linehaul payout per load: a conditional lease write, then the rail, then a token-guarded update."""

from __future__ import annotations

import uuid
from datetime import timedelta

from payhold.clock import fmt
from payhold.store.base import Store


class Crash(Exception):
    """Test hook: raised after the rail call and before the store is updated."""


def pay(store: Store, rail, clock, request_id: str, payout_key: str, amount_cents: int, lease_seconds: int, crash_after_send: bool = False) -> str:
    """Returns sent | duplicate | in_progress."""
    token = uuid.uuid4().hex
    now = clock()
    claimed = store.claim_payout(payout_key, request_id, token, fmt(now + timedelta(seconds=lease_seconds)), fmt(now))
    if not claimed:
        cur = store.get_payout(payout_key)  # consistent read after the conditional failure
        if cur is None or cur.request_id != request_id:
            return "duplicate"
        return "sent" if cur.status == "sent" else "in_progress"
    rail.send(key=payout_key, amount_cents=amount_cents, request_id=request_id)
    if crash_after_send:
        raise Crash(payout_key)
    store.mark_sent(payout_key, token)
    return "sent"
