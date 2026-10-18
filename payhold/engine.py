"""payhold's decider: ingest a packet, run every check against what it has seen, record the outcome."""

from __future__ import annotations

import time

from payhold import config, payout
from payhold.checks import CHECKS
from payhold.checks.base import Context, Reason
from payhold.clock import FixedClock, parse
from payhold.decision import Decision
from payhold.models import Packet, load_key
from payhold.rail import FakeRail
from payhold.registry import Registry
from payhold.store.base import Seen, Store, invoice_key
from payhold.store.memory import MemoryStore


def load_history(store: Store, world: dict) -> None:
    """Pre-stream paid and rejected requests become seen items (and paid payouts) in the store."""
    for status, records in (("paid", world["paid_loads"]), ("rejected", world["rejected_requests"])):
        for r in records:
            lk = load_key(r["broker_usdot"], r["load_no"])
            store.put_seen(Seen(lk, r["factor_id"], r["request_id"], status, r["at"], r["load_no"]))
            store.put_seen(Seen(invoice_key(r["carrier_usdot"], r["invoice_no"]), r["factor_id"], r["request_id"], status, r["at"], r["invoice_no"]))
            if status == "paid":
                pk = f"{lk}#linehaul"
                store.claim_payout(pk, r["request_id"], "history", r["at"], r["at"])
                store.mark_sent(pk, "history")


class Payhold:
    def __init__(self, registry: Registry, store: Store, thresholds: config.Thresholds, clock, rail=None):
        self.registry = registry
        self.store = store
        self.thresholds = thresholds
        self.clock = clock
        self.rail = rail if rail is not None else FakeRail()

    @classmethod
    def from_world(cls, world: dict, store: Store | None = None, thresholds: config.Thresholds | None = None) -> "Payhold":
        store = store if store is not None else MemoryStore()
        load_history(store, world)
        return cls(Registry(world), store, thresholds or config.load(), FixedClock(parse("2000-01-01T00:00:00Z")))

    @property
    def ctx(self) -> Context:
        return Context(self.registry, self.store, self.thresholds)

    def keys(self, packet: Packet) -> list[tuple[str, str]]:
        inv = packet.invoice
        return [
            (packet.load_key, str(packet.ratecon.load_no.norm)),
            (invoice_key(inv.carrier_usdot.norm, inv.invoice_no.norm), str(inv.invoice_no.norm)),
        ]

    def ingest(self, packet: Packet) -> None:
        for pk, label in self.keys(packet):
            self.store.put_seen(Seen(pk, packet.factor_id, packet.request_id, "requested", packet.requested_at, label))

    def decide(self, packet: Packet) -> Decision:
        reasons = tuple(r for r in (check(packet, self.ctx) for check in CHECKS) if r is not None)
        return Decision(request_id=packet.request_id, decision="hold" if reasons else "pay", reasons=reasons)

    def pay(self, packet: Packet) -> str:
        return payout.pay(
            self.store, self.rail, self.clock, packet.request_id, packet.payout_key,
            packet.invoice.total.norm or 0, self.thresholds.payout_lease_seconds,
        )

    def record(self, packet: Packet, decision: Decision) -> None:
        status = "paid" if decision.decision == "pay" else "held"
        for pk, _ in self.keys(packet):
            self.store.set_status(pk, packet.factor_id, packet.request_id, status)
        self.store.append_audit(packet.request_id, packet.requested_at, {"event": "decision", **decision.model_dump(mode="json")})

    def process(self, packet: Packet, timings: dict | None = None) -> Decision:
        """ingest -> decide -> pay (if clean) -> record, on the packet's synthetic clock.

        If `timings` is given, the seconds spent in the checks are stored under "checks".
        """
        self.clock.set(parse(packet.requested_at))
        self.ingest(packet)
        t0 = time.perf_counter()
        d = self.decide(packet)
        if timings is not None:
            timings["checks"] = time.perf_counter() - t0
        if d.decision == "pay":
            result = self.pay(packet)
            if result != "sent":
                d = Decision(
                    request_id=d.request_id,
                    decision="hold",
                    reasons=(Reason(code="payout_" + result, message=f"payout key already claimed ({result})"),),
                )
        self.record(packet, d)
        return d

    def snapshot(self) -> "Payhold":
        """An independent copy of the decider's state. Deciding against it never touches the original."""
        return Payhold(self.registry, self.store.snapshot(), self.thresholds, FixedClock(self.clock()), FakeRail())
