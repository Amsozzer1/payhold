"""Type 3: the load was already requested through a different factor (any status), or paid by one."""

from __future__ import annotations

from payhold.checks.base import Context, Reason, ref
from payhold.models import Packet
from payhold.store.base import invoice_key


def check(packet: Packet, ctx: Context) -> Reason | None:
    rc, inv = packet.ratecon, packet.invoice
    fields = (ref(packet, "ratecon", "load_no"), ref(packet, "bol", "bol_no"))
    other = [
        s for s in ctx.store.seen(packet.load_key) if s.request_id != packet.request_id and s.factor_id != packet.factor_id
    ]
    if other:
        p = other[0]
        return Reason(
            code="double_factoring",
            message=(
                f"load {rc.load_no.norm} from broker USDOT {rc.broker_usdot.norm} already requested through "
                f"{ctx.registry.factor_name(p.factor_id)} at {p.at} (request {p.request_id})"
            ),
            fields=fields,
        )
    paid = [
        s
        for s in ctx.store.seen(invoice_key(inv.carrier_usdot.norm, inv.invoice_no.norm))
        if s.request_id != packet.request_id and s.factor_id != packet.factor_id and s.status == "paid"
    ]
    if paid:
        p = paid[0]
        return Reason(
            code="double_factoring",
            message=(
                f"invoice {inv.invoice_no.norm} from carrier USDOT {inv.carrier_usdot.norm} already paid through "
                f"{ctx.registry.factor_name(p.factor_id)} at {p.at} (request {p.request_id})"
            ),
            fields=(ref(packet, "invoice", "invoice_no"),),
        )
    return None
