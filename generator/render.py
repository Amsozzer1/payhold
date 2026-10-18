"""Renders synthetic rate cons, BOL/PODs and invoices with reportlab, two layouts per doc type.

Labels and column order differ between layouts. Every page carries a SYNTHETIC watermark.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab import rl_config
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

rl_config.invariant = 1  # no timestamps or random IDs in the file, so reruns are byte-identical

FONT = "Helvetica"
BOLD = "Helvetica-Bold"
SIZE = 10
LINE = 16


def fmt_date(iso: str, style: str) -> str:
    d = date.fromisoformat(iso)
    if style == "iso":
        return d.isoformat()
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def fmt_money(cents: int, layout: str) -> str:
    if layout == "A":
        return f"${cents // 100:,}.{cents % 100:02d}"
    return f"{cents // 100}.{cents % 100:02d} USD"


def fmt_load(no: str, layout: str) -> str:
    return no if layout == "A" else f"{no[:3]}-{no[3:]}"


def fmt_bol(no: str, layout: str) -> str:
    return no if layout == "A" else f"{no[:4]} {no[4:]}"


def fmt_invoice(no: str, layout: str) -> str:
    return f"INV-{no}" if layout == "A" else no


class Page:
    def __init__(self, path: Path, title: str):
        self.c = canvas.Canvas(str(path), pagesize=letter, invariant=1)
        self.c.setTitle("SYNTHETIC")
        self.c.setAuthor("payhold synthetic generator")
        self._watermark()
        self.c.setFont(BOLD, 16)
        self.c.drawString(50, 740, title)
        self.c.setFont(FONT, SIZE)

    def _watermark(self) -> None:
        c = self.c
        c.saveState()
        c.setFillColorRGB(0.88, 0.88, 0.88)
        c.setFont(BOLD, 96)
        c.translate(306, 380)
        c.rotate(35)
        c.drawCentredString(0, 0, "SYNTHETIC")
        c.restoreState()

    def text(self, x: float, y: float, s: str, bold: bool = False) -> None:
        self.c.setFont(BOLD if bold else FONT, SIZE)
        self.c.drawString(x, y, s)
        self.c.setFont(FONT, SIZE)

    def right(self, x: float, y: float, s: str) -> None:
        self.c.drawRightString(x, y, s)

    def rule(self, y: float) -> None:
        self.c.setLineWidth(0.5)
        self.c.line(50, y, 562, y)

    def save(self) -> None:
        self.c.setFont(FONT, 7)
        self.c.drawString(50, 30, "SYNTHETIC TEST DOCUMENT generated for payhold. Not a real shipment, carrier or account.")
        self.c.showPage()
        self.c.save()


def render_ratecon(d: dict, path: Path) -> None:
    lay, ds = d["layout"], d["date_style"]
    money = [(it["desc"], fmt_money(it["cents"], lay)) for it in d["items"]]
    total = fmt_money(sum(it["cents"] for it in d["items"]), lay)
    if lay == "A":
        p = Page(path, "RATE CONFIRMATION")
        left = [
            ("Broker:", d["broker_name"]),
            ("Broker USDOT:", d["broker_usdot"]),
            ("Load #:", fmt_load(d["load_no"], lay)),
            ("Revision:", str(d["revision"])),
            ("Origin:", d["origin"]),
            ("Pickup Date:", fmt_date(d["pickup_date"], ds)),
        ]
        right = [
            ("Carrier:", d["carrier_name"]),
            ("Carrier USDOT:", d["carrier_usdot"]),
            ("Destination:", d["dest"]),
            ("Delivery Date:", fmt_date(d["delivery_date"], ds)),
        ]
        y = 700
        for i, (lab, val) in enumerate(left):
            p.text(50, y - i * LINE, f"{lab} {val}")
        for i, (lab, val) in enumerate(right):
            p.text(320, y - i * LINE, f"{lab} {val}")
        y = 580
        p.text(50, y, "Charge", bold=True)
        p.text(470, y, "Amount", bold=True)
        p.rule(y - 5)
        for desc, amt in money:
            y -= LINE
            p.text(50, y, desc)
            p.right(562, y, amt)
        y -= LINE + 6
        p.text(350, y, "Total Rate:", bold=True)
        p.right(562, y, total)
        p.text(50, y - 50, "Carrier agrees to haul the load above at the rate shown. Payment on receipt of signed POD.")
    else:
        p = Page(path, "LOAD TENDER AND RATE AGREEMENT")
        rows = [
            ("Order No.", fmt_load(d["load_no"], lay)),
            ("Agreement Version", str(d["revision"])),
            ("Tendering Broker", d["broker_name"]),
            ("Broker DOT #", d["broker_usdot"]),
            ("Contracted Carrier", d["carrier_name"]),
            ("Carrier DOT #", d["carrier_usdot"]),
            ("Ship Date", fmt_date(d["pickup_date"], ds)),
            ("Origin", d["origin"]),
            ("Delivery Date", fmt_date(d["delivery_date"], ds)),
            ("Destination", d["dest"]),
        ]
        y = 700
        for lab, val in rows:
            p.text(60, y, lab)
            p.text(220, y, val)
            y -= LINE
        y -= 14
        p.text(60, y, "Amount", bold=True)
        p.text(220, y, "Charge", bold=True)
        p.rule(y - 5)
        for desc, amt in money:
            y -= LINE
            p.text(60, y, amt)
            p.text(220, y, desc.upper())
        y -= LINE + 6
        p.text(60, y, "Total Carrier Pay", bold=True)
        p.text(220, y, total)
    p.save()


def render_bol(d: dict, path: Path) -> None:
    lay, ds = d["layout"], d["date_style"]
    if lay == "A":
        p = Page(path, "STRAIGHT BILL OF LADING")
        left = [
            ("BOL No.:", fmt_bol(d["bol_no"], lay)),
            ("Load Ref:", fmt_load(d["load_no"], lay)),
            ("Shipper:", d["shipper"]),
            ("Origin:", d["origin"]),
            ("Pieces:", str(d["pieces"])),
        ]
        right = [
            ("Carrier Name:", d["carrier_name"]),
            ("Carrier USDOT:", d["carrier_usdot"]),
            ("Consignee:", d["consignee"]),
            ("Destination:", d["dest"]),
            ("Weight:", f"{d['weight_lb']:,} lb"),
        ]
        if d["pro_no"]:
            right.append(("PRO #:", d["pro_no"]))
        for i, (lab, val) in enumerate(left):
            p.text(50, 700 - i * LINE, f"{lab} {val}")
        for i, (lab, val) in enumerate(right):
            p.text(320, 700 - i * LINE, f"{lab} {val}")
        y = 560
        p.rule(y + 14)
        p.text(50, y, "PROOF OF DELIVERY", bold=True)
        p.text(50, y - LINE - 4, f"Delivered: {fmt_date(d['delivered_date'], ds)}")
        p.text(50, y - 2 * LINE - 4, f"Received by: {d['received_by']}")
        p.text(50, y - 3 * LINE - 4, "Freight received in good order unless noted.")
    else:
        p = Page(path, "BILL OF LADING / DELIVERY RECEIPT")
        rows = [
            ("B/L Number", fmt_bol(d["bol_no"], lay)),
            ("Customer Order No.", fmt_load(d["load_no"], lay)),
            ("Transporting Carrier", d["carrier_name"].upper().replace(" LLC", ", L.L.C.")),
            ("DOT Number", d["carrier_usdot"]),
        ]
        if d["pro_no"]:
            rows.append(("Pro Number", d["pro_no"]))
        rows += [
            ("Ship From", d["shipper"]),
            ("From City", d["origin"]),
            ("Ship To", d["consignee"]),
            ("To City", d["dest"]),
            ("Handling Units", str(d["pieces"])),
            ("Gross Weight (lb)", str(d["weight_lb"])),
        ]
        y = 700
        for lab, val in rows:
            p.text(60, y, lab)
            p.text(230, y, val)
            y -= LINE
        y -= 20
        p.rule(y + 14)
        p.text(60, y, "DELIVERY RECEIPT", bold=True)
        y -= LINE + 4
        p.text(60, y, "Date Delivered")
        p.text(230, y, fmt_date(d["delivered_date"], ds))
        y -= LINE
        p.text(60, y, "Signed (print name)")
        p.text(230, y, d["received_by"])
    p.save()


def render_invoice(d: dict, path: Path) -> None:
    lay, ds = d["layout"], d["date_style"]
    money = [(it["desc"], fmt_money(it["cents"], lay)) for it in d["items"]]
    total = fmt_money(sum(it["cents"] for it in d["items"]), lay)
    if lay == "A":
        p = Page(path, "INVOICE")
        left = [
            ("From:", d["carrier_name"]),
            ("USDOT:", d["carrier_usdot"]),
            ("Invoice #:", fmt_invoice(d["invoice_no"], lay)),
            ("Invoice Date:", fmt_date(d["invoice_date"], ds)),
        ]
        right = [
            ("Bill To:", d["bill_to"]),
            ("Load #:", fmt_load(d["load_no"], lay)),
            ("BOL #:", fmt_bol(d["bol_no"], lay)),
        ]
        for i, (lab, val) in enumerate(left):
            p.text(50, 700 - i * LINE, f"{lab} {val}")
        for i, (lab, val) in enumerate(right):
            p.text(320, 700 - i * LINE, f"{lab} {val}")
        y = 610
        p.text(50, y, "Description", bold=True)
        p.text(470, y, "Amount", bold=True)
        p.rule(y - 5)
        for desc, amt in money:
            y -= LINE
            p.text(50, y, desc)
            p.right(562, y, amt)
        y -= LINE + 6
        p.text(350, y, "Total Due:", bold=True)
        p.right(562, y, total)
        y -= 40
        p.text(50, y, f"Remit Account: {d['remit_account']}")
        p.text(50, y - LINE, f"Routing: {d['remit_routing']}")
    else:
        p = Page(path, "CARRIER FREIGHT BILL")
        rows = [
            ("Carrier", d["carrier_name"]),
            ("DOT No.", d["carrier_usdot"]),
            ("Bill Number", fmt_invoice(d["invoice_no"], lay)),
            ("Bill Date", fmt_date(d["invoice_date"], ds)),
            ("Customer", d["bill_to"]),
            ("Broker Load No.", fmt_load(d["load_no"], lay)),
            ("B/L No.", fmt_bol(d["bol_no"], lay)),
        ]
        y = 700
        for lab, val in rows:
            p.text(60, y, lab)
            p.text(220, y, val)
            y -= LINE
        y -= 14
        p.text(60, y, "Amount", bold=True)
        p.text(220, y, "Charge", bold=True)
        p.rule(y - 5)
        for desc, amt in money:
            y -= LINE
            p.text(60, y, amt)
            p.text(220, y, desc)
        y -= LINE + 6
        p.text(60, y, "Balance Due", bold=True)
        p.text(220, y, total)
        y -= 40
        p.text(60, y, "Pay To Acct")
        p.text(220, y, d["remit_account"])
        p.text(60, y - LINE, "ABA")
        p.text(220, y - LINE, d["remit_routing"])
    p.save()


def render_packet(docs, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    render_ratecon(docs.ratecon, outdir / "ratecon.pdf")
    render_bol(docs.bol, outdir / "bol.pdf")
    render_invoice(docs.invoice, outdir / "invoice.pdf")
