"""Build Packets and worlds in tests without rendering PDFs. All values are synthetic."""

from __future__ import annotations

from payhold.extract import normalize as nz
from payhold.models import Bol, Field, Invoice, Item, Packet, RateCon

FACTORS = [{"id": "F1", "name": "Alder Funding"}, {"id": "F2", "name": "Birchgate Capital"}]
CARRIER = {
    "id": "C001",
    "legal_name": "Redbird Freight LLC",
    "dba": "Redbird Express",
    "usdot": "99100001",
    "contacts_on_file": ["billing@redbirdfreight.example", "dispatch@redbirdfreight.example", "555-0100-1234"],
    "home_factor": "F1",
    "dedicated": False,
    "remit_history": [
        {"account": "880011112222", "routing": "000111222", "changed_at": "2025-06-01T00:00:00Z", "verified": True, "requested_via": "billing@redbirdfreight.example"}
    ],
}


def world(**extra) -> dict:
    w = {"seed": 0, "carriers": [dict(CARRIER, remit_history=list(CARRIER["remit_history"]))], "brokers": [], "factors": FACTORS, "paid_loads": [], "rejected_requests": []}
    w.update(extra)
    return w


def f(norm, raw=None) -> Field:
    return Field(raw=raw if raw is not None else (None if norm is None else str(norm)), norm=norm, bbox=(10.0, 10.0, 50.0, 20.0), page=0)


def items(*pairs) -> tuple[Item, ...]:
    return tuple(Item(desc=f(nz.desc(d), d), amount=f(c)) for d, c in pairs)


def packet(
    request_id="R1",
    factor_id="F1",
    requested_at="2026-03-02T10:00:00Z",
    broker_usdot="99500001",
    load_no="4820157",
    bol_no="30418827",
    carrier_usdot="99100001",
    carrier_name="Redbird Freight LLC",
    bol_carrier_usdot=None,
    bol_carrier_name=None,
    invoice_no="1043",
    rc_items=(("Linehaul", 185000),),
    inv_items=None,
    received_by="Maria Garcia",
    remit=("880011112222", "000111222"),
) -> Packet:
    inv_items = inv_items if inv_items is not None else rc_items
    rc = RateCon(
        layout="A", broker_name=f("KEYSTONE LOGISTICS"), broker_usdot=f(broker_usdot), load_no=f(load_no),
        revision=f(1), carrier_name=f(nz.name(carrier_name), carrier_name), carrier_usdot=f(carrier_usdot),
        origin=f("Dallas, TX"), pickup_date=f("2026-02-27"), dest=f("Memphis, TN"), delivery_date=f("2026-03-01"),
        items=items(*rc_items), total=f(sum(c for _, c in rc_items)),
    )
    bname = bol_carrier_name or carrier_name
    bol = Bol(
        layout="A", bol_no=f(bol_no), load_no=f(load_no), carrier_name=f(nz.name(bname), bname),
        carrier_usdot=f(bol_carrier_usdot or carrier_usdot), pro_no=f(None), shipper=f("Pinecrest Foods DC"),
        consignee=f("Sunfield Paper Mill"), origin=f("Dallas, TX"), dest=f("Memphis, TN"), pieces=f(6),
        weight_lb=f(24000), delivered_date=f("2026-03-01"), received_by=f(received_by),
    )
    inv = Invoice(
        layout="A", carrier_name=f(nz.name(carrier_name), carrier_name), carrier_usdot=f(carrier_usdot),
        invoice_no=f(invoice_no), invoice_date=f("2026-03-01"), bill_to=f("KEYSTONE LOGISTICS"), load_no=f(load_no),
        bol_no=f(bol_no), items=items(*inv_items), total=f(sum(c for _, c in inv_items)),
        remit_account=f(remit[0]), remit_routing=f(remit[1]),
    )
    return Packet(request_id=request_id, factor_id=factor_id, requested_at=requested_at, ratecon=rc, bol=bol, invoice=inv)
