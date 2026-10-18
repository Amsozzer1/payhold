"""pay(event, context): claim the payout key, call the rail once, record the outcome."""

from __future__ import annotations

from payhold.checks.base import Reason
from payhold.clock import parse
from payhold.decision import Decision
from payhold.handlers import runtime
from payhold.models import Packet


def handler(event: dict, context=None) -> dict:
    ph = runtime.get()
    packet = Packet.model_validate(event["packet"])
    ph.clock.set(parse(packet.requested_at))
    result = ph.pay(packet)
    if result == "sent":
        decision = Decision(request_id=packet.request_id, decision="pay")
    else:
        reason = Reason(code=f"payout_{result}", message=f"payout key already claimed ({result})")
        decision = Decision(request_id=packet.request_id, decision="hold", reasons=(reason,))
    ph.record(packet, decision)
    return {"result": result, "decision": decision.model_dump(mode="json")}
