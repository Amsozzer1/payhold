"""Type 4: remit-to doesn't match the file, or changed recently without verification from a known contact."""

from __future__ import annotations

from datetime import timedelta

from payhold.checks.base import Context, Reason, ref
from payhold.clock import parse
from payhold.models import Packet
from payhold.registry import Registry


def check(packet: Packet, ctx: Context) -> Reason | None:
    inv = packet.invoice
    fields = (ref(packet, "invoice", "remit_account"), ref(packet, "invoice", "remit_routing"))
    carrier = ctx.registry.carrier(inv.carrier_usdot.norm)
    if carrier is None:
        return Reason(code="unknown_carrier", message=f"carrier USDOT {inv.carrier_usdot.norm} not on file", fields=fields)
    current = Registry.remit_at(carrier, packet.requested_at)
    if current is None or (inv.remit_account.norm, inv.remit_routing.norm) != (current["account"], current["routing"]):
        return Reason(
            code="remit_mismatch",
            message=f"invoice remit-to account {inv.remit_account.norm} is not the account on file for USDOT {inv.carrier_usdot.norm}",
            fields=fields,
        )
    age = parse(packet.requested_at) - parse(current["changed_at"])
    recent = age <= timedelta(days=ctx.thresholds.remit_recent_change_days)
    known_contact = current["requested_via"] in carrier["contacts_on_file"]
    if recent and not current["verified"] and not known_contact:
        return Reason(
            code="bank_change",
            message=(
                f"remit-to changed {age.days} days ago, not verified, requested via {current['requested_via']} "
                f"which is not a contact on file"
            ),
            fields=fields,
        )
    return None
