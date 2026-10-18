"""Type 2: the same factor already has this load or this invoice number, paid or pending."""

from __future__ import annotations

from payhold.checks.base import Context, Reason, ref
from payhold.models import Packet
from payhold.store.base import invoice_key


def check(packet: Packet, ctx: Context) -> Reason | None:
    inv = packet.invoice
    for pk, what, fields in (
        (packet.load_key, f"load {packet.ratecon.load_no.norm}", ("ratecon", "load_no")),
        (invoice_key(inv.carrier_usdot.norm, inv.invoice_no.norm), f"invoice {inv.invoice_no.norm}", ("invoice", "invoice_no")),
    ):
        prior = [
            s
            for s in ctx.store.seen(pk)
            if s.request_id != packet.request_id and s.factor_id == packet.factor_id and s.status != "rejected"
        ]
        if prior:
            p = prior[0]
            return Reason(
                code="duplicate_rebill",
                message=f"{what} already {p.status} through {ctx.registry.factor_name(p.factor_id)} at {p.at} (request {p.request_id})",
                fields=(ref(packet, *fields),),
            )
    return None
