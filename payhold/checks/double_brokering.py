"""Type 5: the carrier on the BOL/POD is not the carrier on the rate con."""

from __future__ import annotations

from payhold.checks.base import Context, Reason, ref
from payhold.extract import normalize as nz
from payhold.models import Packet


def check(packet: Packet, ctx: Context) -> Reason | None:
    rc, bol = packet.ratecon, packet.bol
    fields = (ref(packet, "bol", "carrier_name"), ref(packet, "bol", "carrier_usdot"), ref(packet, "ratecon", "carrier_usdot"))
    if bol.carrier_usdot.norm != rc.carrier_usdot.norm:
        return Reason(
            code="double_brokering",
            message=f"BOL carrier USDOT {bol.carrier_usdot.norm} differs from rate con carrier USDOT {rc.carrier_usdot.norm}",
            fields=fields,
        )
    # Names on file for this USDOT: the rate con's name, plus the registry's legal name and DBA.
    names = {rc.carrier_name.norm}
    carrier = ctx.registry.carrier(rc.carrier_usdot.norm)
    if carrier:
        names |= {nz.name(carrier["legal_name"]), nz.name(carrier["dba"])}
    if bol.carrier_name.norm not in names:
        return Reason(
            code="double_brokering",
            message=f"BOL carrier name '{bol.carrier_name.raw}' does not match rate con carrier '{rc.carrier_name.raw}'",
            fields=fields,
        )
    return None
