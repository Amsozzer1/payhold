"""Ground-truth validator for the held-out set. Checks world and history facts only; never calls a decider.

Each held-out packet must be clean apart from its one feature:
  - requested after the end of the main stream
  - carrier on file, same USDOT on all three documents, no unverified remit-to change within N days
  - invoice remit-to is the account on file at request time
  - invoice bills exactly the rate con charges; POD signed; documents agree on load and BOL numbers
  - invoice number continues the carrier's sequence past every main-stream and history value
  - load and BOL numbers are fresh, except kind 2's deliberate load number
  - kind 1: the BOL prints the carrier's DBA, rate con and invoice print the legal name
  - kind 2: the load number was paid pre-stream under the same factor by a different broker

python -m generator.validate_heldout data/seed-1 [data/seed-2 ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from generator import settings
from generator.heldout import remit_at, ts, unverified_recent_change


def validate(seed_dir: Path) -> list[str]:
    world = json.loads((seed_dir / "world.json").read_text())
    main = json.loads((seed_dir / "truth.json").read_text())["packets"]
    held = json.loads((seed_dir / "heldout_truth.json").read_text())["packets"]
    requests = {r["request_id"]: r for r in json.loads((seed_dir / "heldout_requests.json").read_text())}
    main_requests = json.loads((seed_dir / "requests.json").read_text())
    carriers = {c["usdot"]: c for c in world["carriers"]}
    brokers = {b["usdot"] for b in world["brokers"]}
    end = max(ts(r["requested_at"]) for r in main_requests)

    history = world["paid_loads"] + world["rejected_requests"]
    used_loads = {(p["docs"]["ratecon"]["broker_usdot"], p["docs"]["ratecon"]["load_no"]) for p in main}
    used_loads |= {(h["broker_usdot"], h["load_no"]) for h in history}
    used_load_nos = {ln for _, ln in used_loads}
    used_bols = {p["docs"]["bol"]["bol_no"] for p in main}
    last_invoice: dict[str, int] = {}
    for usdot, inv in [(p["docs"]["invoice"]["carrier_usdot"], p["docs"]["invoice"]["invoice_no"]) for p in main] + [
        (h["carrier_usdot"], h["invoice_no"]) for h in history
    ]:
        last_invoice[usdot] = max(last_invoice.get(usdot, 0), int(inv))

    errors: list[str] = []
    seen_invoices: set[tuple[str, str]] = set()
    seen_loads: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for p in held:
        rid, kind = p["request_id"], p["lookalike"]
        counts[kind] = counts.get(kind, 0) + 1
        rc, bol, inv = p["docs"]["ratecon"], p["docs"]["bol"], p["docs"]["invoice"]

        def err(msg: str) -> None:
            errors.append(f"{rid} ({kind}): {msg}")

        at = ts(requests[rid]["requested_at"])
        if at <= end:
            err("requested inside the main stream")
        carrier = carriers.get(rc["carrier_usdot"])
        if carrier is None:
            err("carrier not on file")
            continue
        if not (rc["carrier_usdot"] == bol["carrier_usdot"] == inv["carrier_usdot"]):
            err("USDOT differs between documents")
        if unverified_recent_change(carrier, at, settings.HELDOUT_REMIT_EXCLUDE_DAYS):
            err("carrier has an unverified recent remit-to change")
        cur = remit_at(carrier, at)
        if (inv["remit_account"], inv["remit_routing"]) != (cur["account"], cur["routing"]):
            err("remit-to is not the account on file")
        if [(i["desc"], i["cents"]) for i in inv["items"]] != [(i["desc"], i["cents"]) for i in rc["items"]]:
            err("invoice charges differ from the rate con")
        if not bol["received_by"]:
            err("POD not signed")
        if not (rc["load_no"] == bol["load_no"] == inv["load_no"]) or inv["bol_no"] != bol["bol_no"]:
            err("documents disagree on load or BOL number")
        if int(inv["invoice_no"]) <= last_invoice.get(inv["carrier_usdot"], 0):
            err(f"invoice {inv['invoice_no']} does not continue the carrier's sequence")
        if (inv["carrier_usdot"], inv["invoice_no"]) in seen_invoices:
            err("invoice number reused inside the held-out set")
        seen_invoices.add((inv["carrier_usdot"], inv["invoice_no"]))
        if bol["bol_no"] in used_bols:
            err("BOL number is not fresh")
        if rc["broker_usdot"] not in brokers:
            err("broker not on file")
        if inv["bill_to"] != rc["broker_name"]:
            err("invoice billed to a different broker")
        key = (rc["broker_usdot"], rc["load_no"])
        if key in used_loads or key in seen_loads:
            err("broker + load number already used")
        seen_loads.add(key)
        if p["factor_id"] != carrier["home_factor"]:
            err("not submitted through the carrier's factor")

        if kind == "dba_on_bol":
            if not carrier["dba"] or bol["carrier_name"] != carrier["dba"]:
                err("BOL does not print the DBA")
            if rc["carrier_name"] != carrier["legal_name"] or inv["carrier_name"] != carrier["legal_name"]:
                err("rate con or invoice does not print the legal name")
            if rc["load_no"] in used_load_nos:
                err("load number is not fresh")
        elif kind == "same_load_no_other_broker":
            if bol["carrier_name"] != carrier["legal_name"]:
                err("BOL does not print the legal name")
            prior = [h for h in world["paid_loads"] if h["load_no"] == rc["load_no"]]
            if not any(h["factor_id"] == p["factor_id"] and h["broker_usdot"] != rc["broker_usdot"] for h in prior):
                err("no pre-stream paid load with this number under the same factor from another broker")
        else:
            err("unknown kind")

    for kind in ("dba_on_bol", "same_load_no_other_broker"):
        if counts.get(kind) != settings.HELDOUT_PER_KIND:
            errors.append(f"{seed_dir}: {counts.get(kind, 0)} packets of {kind}, want {settings.HELDOUT_PER_KIND}")
    return errors


def main(argv: list[str]) -> int:
    bad = 0
    for arg in argv:
        errors = validate(Path(arg))
        print(f"{arg}: {'ok' if not errors else f'{len(errors)} problems'}")
        for e in errors[:20]:
            print(f"  {e}")
        bad += len(errors)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
