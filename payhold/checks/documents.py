"""Cross-document consistency and proof of delivery. Not a planted issue type; these keep bad paperwork out."""

from __future__ import annotations

from payhold.checks.base import Context, Reason, ref
from payhold.models import Packet


def check(packet: Packet, ctx: Context) -> Reason | None:
    rc, bol, inv = packet.ratecon, packet.bol, packet.invoice
    if not bol.received_by.norm:
        return Reason(code="pod_missing", message="POD has no 'received by' name", fields=(ref(packet, "bol", "received_by"),))
    pairs = [
        (bol.load_no.norm == rc.load_no.norm, "BOL load reference", ("bol", "load_no")),
        (inv.load_no.norm == rc.load_no.norm, "invoice load number", ("invoice", "load_no")),
        (inv.bol_no.norm == bol.bol_no.norm, "invoice BOL number", ("invoice", "bol_no")),
        (inv.carrier_usdot.norm == rc.carrier_usdot.norm, "invoice carrier USDOT", ("invoice", "carrier_usdot")),
    ]
    for ok, what, f in pairs:
        if not ok:
            return Reason(code="doc_mismatch", message=f"{what} does not match the other documents", fields=(ref(packet, *f),))
    return None
