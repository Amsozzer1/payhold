"""Label anchors for the known layouts. A layout is detected from which labels are present."""

from __future__ import annotations

from dataclasses import dataclass

from payhold.extract import normalize as nz


@dataclass(frozen=True)
class Table:
    header: tuple[str, str]  # header words, left to right
    amount_col: int  # which header column holds the amount (0 or 1)
    total_label: str


@dataclass(frozen=True)
class Layout:
    name: str
    labels: dict[str, str]  # field -> label text
    optional: frozenset[str] = frozenset()
    table: Table | None = None


RATECON = [
    Layout(
        "A",
        {
            "broker_name": "Broker:",
            "broker_usdot": "Broker USDOT:",
            "load_no": "Load #:",
            "revision": "Revision:",
            "origin": "Origin:",
            "pickup_date": "Pickup Date:",
            "carrier_name": "Carrier:",
            "carrier_usdot": "Carrier USDOT:",
            "dest": "Destination:",
            "delivery_date": "Delivery Date:",
            "total": "Total Rate:",
        },
        table=Table(("Charge", "Amount"), 1, "Total Rate:"),
    ),
    Layout(
        "B",
        {
            "load_no": "Order No.",
            "revision": "Agreement Version",
            "broker_name": "Tendering Broker",
            "broker_usdot": "Broker DOT #",
            "carrier_name": "Contracted Carrier",
            "carrier_usdot": "Carrier DOT #",
            "pickup_date": "Ship Date",
            "origin": "Origin",
            "delivery_date": "Delivery Date",
            "dest": "Destination",
            "total": "Total Carrier Pay",
        },
        table=Table(("Amount", "Charge"), 0, "Total Carrier Pay"),
    ),
]

BOL = [
    Layout(
        "A",
        {
            "bol_no": "BOL No.:",
            "load_no": "Load Ref:",
            "shipper": "Shipper:",
            "origin": "Origin:",
            "pieces": "Pieces:",
            "carrier_name": "Carrier Name:",
            "carrier_usdot": "Carrier USDOT:",
            "consignee": "Consignee:",
            "dest": "Destination:",
            "weight_lb": "Weight:",
            "pro_no": "PRO #:",
            "delivered_date": "Delivered:",
            "received_by": "Received by:",
        },
        optional=frozenset({"pro_no", "received_by"}),
    ),
    Layout(
        "B",
        {
            "bol_no": "B/L Number",
            "load_no": "Customer Order No.",
            "carrier_name": "Transporting Carrier",
            "carrier_usdot": "DOT Number",
            "pro_no": "Pro Number",
            "shipper": "Ship From",
            "origin": "From City",
            "consignee": "Ship To",
            "dest": "To City",
            "pieces": "Handling Units",
            "weight_lb": "Gross Weight (lb)",
            "delivered_date": "Date Delivered",
            "received_by": "Signed (print name)",
        },
        optional=frozenset({"pro_no", "received_by"}),
    ),
]

INVOICE = [
    Layout(
        "A",
        {
            "carrier_name": "From:",
            "carrier_usdot": "USDOT:",
            "invoice_no": "Invoice #:",
            "invoice_date": "Invoice Date:",
            "bill_to": "Bill To:",
            "load_no": "Load #:",
            "bol_no": "BOL #:",
            "total": "Total Due:",
            "remit_account": "Remit Account:",
            "remit_routing": "Routing:",
        },
        table=Table(("Description", "Amount"), 1, "Total Due:"),
    ),
    Layout(
        "B",
        {
            "carrier_name": "Carrier",
            "carrier_usdot": "DOT No.",
            "invoice_no": "Bill Number",
            "invoice_date": "Bill Date",
            "bill_to": "Customer",
            "load_no": "Broker Load No.",
            "bol_no": "B/L No.",
            "total": "Balance Due",
            "remit_account": "Pay To Acct",
            "remit_routing": "ABA",
        },
        table=Table(("Amount", "Charge"), 0, "Balance Due"),
    ),
]

# How each field is normalized, whatever the document.
NORMALIZERS = {
    "broker_name": nz.name,
    "carrier_name": nz.name,
    "bill_to": nz.name,
    "broker_usdot": nz.digits,
    "carrier_usdot": nz.digits,
    "load_no": nz.load_no,
    "bol_no": nz.bol_no,
    "invoice_no": nz.invoice_no,
    "pro_no": nz.ident,
    "revision": nz.integer,
    "pieces": nz.integer,
    "weight_lb": nz.integer,
    "pickup_date": nz.date,
    "delivery_date": nz.date,
    "delivered_date": nz.date,
    "invoice_date": nz.date,
    "total": nz.money,
    "remit_account": nz.digits,
    "remit_routing": nz.digits,
    "origin": nz.text,
    "dest": nz.text,
    "shipper": nz.text,
    "consignee": nz.text,
    "received_by": nz.text,
}
