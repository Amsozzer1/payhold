"""The baseline: what one factor's back office automates on day one.

No NOA tracking, broker verification or lien search, and it only sees its own factor's book.
Pay if the invoice total is at most the rate con total, the POD has a 'received by' name, and neither
(broker USDOT, load number) nor (carrier USDOT, invoice number) is already paid or pending through this
same factor. Rejected requests don't count. In the eval, pending means held.
"""

from __future__ import annotations

import copy

from payhold.checks.base import Reason
from payhold.decision import Decision
from payhold.models import Packet


class Baseline:
    def __init__(self, world: dict | None = None):
        self.books: dict[str, dict[str, dict]] = {}
        for r in (world or {}).get("paid_loads", []):
            book = self.book(r["factor_id"])
            book["loads"][(r["broker_usdot"], r["load_no"])] = "paid"
            book["invoices"][(r["carrier_usdot"], r["invoice_no"])] = "paid"

    def book(self, factor_id: str) -> dict:
        return self.books.setdefault(factor_id, {"loads": {}, "invoices": {}})

    @staticmethod
    def keys(packet: Packet) -> tuple[tuple, tuple]:
        rc, inv = packet.ratecon, packet.invoice
        return (rc.broker_usdot.norm, rc.load_no.norm), (inv.carrier_usdot.norm, inv.invoice_no.norm)

    def decide(self, packet: Packet) -> Decision:
        reasons = []
        if (packet.invoice.total.norm or 0) > (packet.ratecon.total.norm or 0):
            reasons.append(Reason(code="baseline_over_rate_con", message="invoice total exceeds rate con total"))
        if not packet.bol.received_by.norm:
            reasons.append(Reason(code="baseline_pod_missing", message="POD has no 'received by' name"))
        book = self.book(packet.factor_id)
        lk, ik = self.keys(packet)
        if lk in book["loads"]:
            reasons.append(Reason(code="baseline_duplicate_load", message=f"load already {book['loads'][lk]} through this factor"))
        if ik in book["invoices"]:
            reasons.append(Reason(code="baseline_duplicate_invoice", message=f"invoice already {book['invoices'][ik]} through this factor"))
        return Decision(request_id=packet.request_id, decision="hold" if reasons else "pay", reasons=tuple(reasons))

    def record(self, packet: Packet, decision: Decision) -> None:
        status = "paid" if decision.decision == "pay" else "held"
        book = self.book(packet.factor_id)
        lk, ik = self.keys(packet)
        book["loads"][lk] = status
        book["invoices"][ik] = status

    def process(self, packet: Packet) -> Decision:
        d = self.decide(packet)
        self.record(packet, d)
        return d

    def snapshot(self) -> "Baseline":
        b = Baseline()
        b.books = copy.deepcopy(self.books)
        return b
