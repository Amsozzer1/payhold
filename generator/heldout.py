"""Held-out look-alikes: a separate stream written after the freeze commit.

Two kinds, 25 packets each per seed, from default_rng([seed, 2]) against the same world:
  dba_on_bol                 the BOL/POD prints the carrier's DBA; rate con and invoice print the legal name
  same_load_no_other_broker  a load number already paid under the same factor, but from a different broker

The main stream is rebuilt from its own RNG first and never written, so it cannot change. Rendering goes
through the existing layouts and labels; only values change.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from generator import settings
from generator.__main__ import dump
from generator.build import Builder, Docs, Packet, iso
from generator.render import render_packet

KINDS = ["dba_on_bol", "same_load_no_other_broker"]
LABELS = {
    "dba_on_bol": "DBA name on BOL/POD",
    "same_load_no_other_broker": "same load number, different broker (confirms key scoping)",
}


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def unverified_recent_change(carrier: dict, at: datetime, days: int) -> bool:
    return any(
        not r["verified"] and timedelta(0) <= at - ts(r["changed_at"]) <= timedelta(days=days)
        for r in carrier["remit_history"]
    )


def remit_at(carrier: dict, at: datetime) -> dict:
    """The remit-to entry in effect at `at` (latest change at or before it), from world facts."""
    return max((r for r in carrier["remit_history"] if ts(r["changed_at"]) <= at), key=lambda r: ts(r["changed_at"]))


def build_heldout(seed: int, n: int) -> tuple[dict, list[Packet], dict]:
    """Returns (world json, held-out packets, the main stream's end time and counters for validation)."""
    b = Builder(seed, n)
    world, main = b.build()  # same seed, same RNG: the main stream exactly as `make gen` wrote it
    end = main[-1].requested_at
    b.rng = np.random.default_rng([seed, 2])  # everything below draws from the held-out RNG only

    kinds = [k for k in KINDS for _ in range(settings.HELDOUT_PER_KIND)]
    kinds = [kinds[i] for i in b.rng.permutation(len(kinds))]
    paid_pool = [int(i) for i in b.rng.permutation(len(world.paid_loads))]

    packets: list[Packet] = []
    for k, kind in enumerate(kinds, start=1):
        at = end + timedelta(minutes=k)
        eligible = [
            c for c in world.carriers if not unverified_recent_change(c, at, settings.HELDOUT_REMIT_EXCLUDE_DAYS)
        ]
        if kind == "dba_on_bol":
            carrier = b.pick([c for c in eligible if c["dba"]])
            delivered = (at - timedelta(days=int(b.rng.integers(0, 4)))).date()
            load = b.make_load(world, carrier["id"], delivered, b.chance(settings.SHARE_WITH_AGREED_ACCESSORIAL))
            hauler = dict(carrier, legal_name=carrier["dba"])  # same USDOT, DBA printed as the name
        else:
            while True:
                prior = world.paid_loads[paid_pool.pop()]
                same_factor = [c for c in eligible if c["home_factor"] == prior["factor_id"]]
                if same_factor:
                    break
            carrier = b.pick(same_factor)
            delivered = (at - timedelta(days=int(b.rng.integers(0, 4)))).date()
            load = b.make_load(world, carrier["id"], delivered, b.chance(settings.SHARE_WITH_AGREED_ACCESSORIAL))
            while world.broker(load.broker_id)["usdot"] == prior["broker_usdot"]:
                load.broker_id = b.pick(world.brokers)["id"]
            load.load_no = prior["load_no"]  # the deliberate collision: same number, different broker
            hauler = None
        invoice_no = b.take_invoice_no(carrier["id"])
        invoice_date = min(delivered + timedelta(days=int(b.rng.integers(0, 2))), at.date())
        remit = remit_at(carrier, at)
        docs = Docs(
            ratecon=b.ratecon_doc(world, load),
            bol=b.bol_doc(world, load, hauler),
            invoice=b.invoice_doc(world, load, invoice_no, invoice_date, list(load.items), remit),
        )
        packets.append(Packet(f"S{seed}-X{k:03d}", n + k - 1, carrier["home_factor"], at, 0, 0, kind, None, docs))
    facts = {"end_of_stream": iso(end), "main_packets": main}
    return world.to_json(), packets, facts


def generate_heldout(seed: int, seed_dir: Path) -> list[Packet]:
    truth = json.loads((seed_dir / "truth.json").read_text())
    world_json, packets, _ = build_heldout(seed, truth["n"])
    if world_json != json.loads((seed_dir / "world.json").read_text()):
        raise SystemExit("rebuilt world differs from world.json: regenerate the main stream first")
    out = seed_dir / "heldout"
    for p in packets:
        render_packet(p.docs, out / "pdfs" / p.request_id)
    dump(
        [
            {
                "request_id": p.request_id,
                "factor_id": p.factor_id,
                "requested_at": iso(p.requested_at),
                "docs": {k: f"heldout/pdfs/{p.request_id}/{k}.pdf" for k in ("ratecon", "bol", "invoice")},
            }
            for p in packets
        ],
        seed_dir / "heldout_requests.json",
    )
    dump(
        {
            "synthetic": True,
            "seed": seed,
            "labels": LABELS,
            "packets": [
                {
                    "request_id": p.request_id,
                    "seq": p.seq,
                    "factor_id": p.factor_id,
                    "issue_type": 0,
                    "issue_name": "clean",
                    "exposure_cents": 0,
                    "lookalike": p.lookalike,
                    "anchor_request_id": None,
                    "docs": {"ratecon": p.docs.ratecon, "bol": p.docs.bol, "invoice": p.docs.invoice},
                }
                for p in packets
            ],
        },
        seed_dir / "heldout_truth.json",
    )
    return packets
