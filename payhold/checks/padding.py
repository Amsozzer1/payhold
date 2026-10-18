"""Type 1: the invoice bills a charge the rate con doesn't have, or more than it agreed."""

from __future__ import annotations

from payhold.checks.base import Context, Reason, dollars, ref
from payhold.models import Packet


def check(packet: Packet, ctx: Context) -> Reason | None:
    agreed: dict[str, int] = {}
    for it in packet.ratecon.items:
        agreed[it.desc.norm] = agreed.get(it.desc.norm, 0) + (it.amount.norm or 0)
    billed: dict[str, int] = {}
    raw: dict[str, str] = {}
    for it in packet.invoice.items:
        billed[it.desc.norm] = billed.get(it.desc.norm, 0) + (it.amount.norm or 0)
        raw[it.desc.norm] = it.desc.raw
    extra = [(raw[d], amt - agreed.get(d, 0)) for d, amt in billed.items() if amt > agreed.get(d, 0)]
    rc_total = packet.ratecon.total.norm or 0
    inv_total = packet.invoice.total.norm or 0
    over = inv_total - rc_total
    if not extra and over <= ctx.thresholds.padding_tolerance_cents:
        return None
    parts = [f"{d} {dollars(a)} not on rate con" for d, a in extra]
    parts.append(f"invoice total {dollars(inv_total)} vs rate con total {dollars(rc_total)}")
    return Reason(
        code="padding",
        message="; ".join(parts),
        fields=(ref(packet, "invoice", "total"), ref(packet, "ratecon", "total")),
    )
