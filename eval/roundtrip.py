"""Extraction round-trip: every field of every PDF against the generator's spec.

python -m eval.roundtrip data/seed-1 data/seed-101 ...
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from payhold.extract import normalize as nz
from payhold.extract.pdf import extract_packet

TEXT = ("origin", "dest", "shipper", "consignee", "received_by")


def expected(doc_type: str, d: dict) -> dict:
    """Normalized values the extractor should return for one spec."""
    e: dict = {}
    if doc_type == "ratecon":
        e = {
            "broker_name": nz.name(d["broker_name"]),
            "broker_usdot": d["broker_usdot"],
            "load_no": d["load_no"],
            "revision": d["revision"],
            "carrier_name": nz.name(d["carrier_name"]),
            "carrier_usdot": d["carrier_usdot"],
            "pickup_date": d["pickup_date"],
            "delivery_date": d["delivery_date"],
        }
    elif doc_type == "bol":
        e = {
            "bol_no": d["bol_no"],
            "load_no": d["load_no"],
            "carrier_name": nz.name(d["carrier_name"]),
            "carrier_usdot": d["carrier_usdot"],
            "pro_no": d["pro_no"],
            "pieces": d["pieces"],
            "weight_lb": d["weight_lb"],
            "delivered_date": d["delivered_date"],
            "shipper": d["shipper"],
            "consignee": d["consignee"],
            "received_by": d["received_by"],
        }
    else:
        e = {
            "carrier_name": nz.name(d["carrier_name"]),
            "carrier_usdot": d["carrier_usdot"],
            "invoice_no": d["invoice_no"],
            "invoice_date": d["invoice_date"],
            "bill_to": nz.name(d["bill_to"]),
            "load_no": d["load_no"],
            "bol_no": d["bol_no"],
            "remit_account": d["remit_account"],
            "remit_routing": d["remit_routing"],
        }
    for k in ("origin", "dest"):
        if k in d:
            e[k] = d[k]
    if "items" in d:
        e["items"] = [(nz.desc(it["desc"]), it["cents"]) for it in d["items"]]
        e["total"] = sum(it["cents"] for it in d["items"])
    return e


def got(doc, field: str):
    if field == "items":
        return [(it.desc.norm, it.amount.norm) for it in doc.items]
    return getattr(doc, field).norm


def check_seed(seed_dir: Path) -> tuple[int, Counter, list[str]]:
    """Returns (fields checked, failures by doc.field, failure details)."""
    requests = json.loads((seed_dir / "requests.json").read_text())
    truth = {p["request_id"]: p for p in json.loads((seed_dir / "truth.json").read_text())["packets"]}
    checked, fails, details = 0, Counter(), []
    for req in requests:
        packet = extract_packet(req, seed_dir)
        spec = truth[req["request_id"]]["docs"]
        for doc_type in ("ratecon", "bol", "invoice"):
            doc = getattr(packet, doc_type)
            if doc.layout != spec[doc_type]["layout"]:
                fails[f"{doc_type}.layout"] += 1
                details.append(f"{req['request_id']} {doc_type}.layout {doc.layout} != {spec[doc_type]['layout']}")
            for field, want in expected(doc_type, spec[doc_type]).items():
                checked += 1
                have = got(doc, field)
                ok = have == want
                if ok and field != "items" and want is not None:
                    ok = getattr(doc, field).bbox is not None
                if not ok:
                    key = f"{doc_type}.{field}"
                    fails[key] += 1
                    details.append(f"{req['request_id']} {key}: got {have!r}, want {want!r}")
    return checked, fails, details


def main(argv: list[str]) -> int:
    bad = 0
    for arg in argv:
        checked, fails, details = check_seed(Path(arg))
        print(f"{arg}: {checked} fields checked, {sum(fails.values())} failures")
        for key, n in sorted(fails.items()):
            print(f"  {key}: {n}")
        for line in details[:20]:
            print(f"    {line}")
        bad += sum(fails.values())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
