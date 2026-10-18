"""decide(event, context): run every check. A hold is recorded here; a pay goes on to the pay handler."""

from __future__ import annotations

from payhold.handlers import runtime
from payhold.models import Packet


def handler(event: dict, context=None) -> dict:
    ph = runtime.get()
    packet = Packet.model_validate(event["packet"])
    decision = ph.decide(packet)
    if decision.decision == "hold":
        ph.record(packet, decision)
    return {"packet": event["packet"], "decision": decision.model_dump(mode="json")}
