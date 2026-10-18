"""Builds a seeded synthetic world and a packet stream with planted issues and look-alikes.

Everything here is synthetic. Identifiers come from above the issued range (USDOT 99xxxxxx),
domains are .example, and routing numbers start with 000, which no real bank uses.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from generator import names, settings


@dataclass
class LineItem:
    desc: str
    cents: int


@dataclass
class Load:
    """One physical shipment. The rate con and BOL are rendered from this."""

    broker_id: str
    carrier_id: str
    load_no: str  # 7 digits
    bol_no: str  # 8 digits
    pro_no: str | None
    origin: str
    dest: str
    pickup: date
    delivered: date
    shipper: str
    consignee: str
    pieces: int
    weight_lb: int
    received_by: str
    items: list[LineItem]
    revision: int = 1


@dataclass
class Docs:
    """Everything needed to render the three PDFs of one packet."""

    ratecon: dict
    bol: dict
    invoice: dict


@dataclass
class Packet:
    request_id: str
    seq: int
    factor_id: str
    requested_at: datetime
    issue_type: int
    exposure_cents: int
    lookalike: str | None
    anchor_request_id: str | None
    docs: Docs


@dataclass
class World:
    seed: int
    carriers: list[dict] = field(default_factory=list)
    brokers: list[dict] = field(default_factory=list)
    factors: list[dict] = field(default_factory=list)
    paid_loads: list[dict] = field(default_factory=list)
    rejected_requests: list[dict] = field(default_factory=list)

    def carrier(self, cid: str) -> dict:
        return self._carriers[cid]

    def broker(self, bid: str) -> dict:
        return self._brokers[bid]

    def index(self) -> None:
        self._carriers = {c["id"]: c for c in self.carriers}
        self._brokers = {b["id"]: b for b in self.brokers}

    def to_json(self) -> dict:
        """What payhold is allowed to see: registry, remit-to history, factors, pre-stream history."""
        return {
            "synthetic": True,
            "seed": self.seed,
            "carriers": self.carriers,
            "brokers": self.brokers,
            "factors": self.factors,
            "paid_loads": self.paid_loads,
            "rejected_requests": self.rejected_requests,
        }


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


class Builder:
    def __init__(self, seed: int, n: int):
        self.seed = seed
        self.n = n
        self.rng = np.random.default_rng(seed)
        self.used_load_nos: set[str] = set()
        self.used_bol_nos: set[str] = set()
        self.used_usdots: set[str] = set()
        self.next_invoice: dict[str, int] = {}
        self.history_loads: dict[str, Load] = {}  # history request_id -> load

    # ---- small helpers -------------------------------------------------------------------

    def pick(self, seq):
        return seq[int(self.rng.integers(len(seq)))]

    def chance(self, p: float) -> bool:
        return bool(self.rng.random() < p)

    def usdot(self, lo: int, hi: int) -> str:
        while True:
            v = f"99{int(self.rng.integers(lo, hi)):06d}"
            if v not in self.used_usdots:
                self.used_usdots.add(v)
                return v

    def load_no(self) -> str:
        while True:
            v = f"{int(self.rng.integers(1_000_000, 9_999_999))}"
            if v not in self.used_load_nos:
                self.used_load_nos.add(v)
                return v

    def bol_no(self) -> str:
        while True:
            v = f"{int(self.rng.integers(10_000_000, 99_999_999))}"
            if v not in self.used_bol_nos:
                self.used_bol_nos.add(v)
                return v

    def person(self) -> str:
        return f"{self.pick(names.PERSON_FIRST)} {self.pick(names.PERSON_LAST)}"

    def city(self) -> str:
        c, s = self.pick(names.CITIES)
        return f"{c}, {s}"

    def account(self) -> tuple[str, str]:
        acct = f"8800{int(self.rng.integers(10_000_000, 99_999_999))}"
        routing = f"000{int(self.rng.integers(100_000, 999_999))}"
        return acct, routing

    def take_invoice_no(self, carrier_id: str) -> str:
        v = self.next_invoice[carrier_id]
        self.next_invoice[carrier_id] = v + 1
        return str(v)

    def money(self, lo: int, hi: int, step: int = 25) -> int:
        """Dollar amount in [lo, hi] rounded to `step`, returned in cents."""
        return int(self.rng.integers(lo // step, hi // step + 1)) * step * 100

    # ---- world ---------------------------------------------------------------------------

    def build_world(self, dedicated: int) -> World:
        w = World(seed=self.seed)
        w.factors = [{"id": fid, "name": fname} for fid, fname in settings.FACTORS]

        used_names: set[str] = set()
        total = settings.GENERAL_CARRIERS + dedicated
        dba_ids = set(
            self.rng.choice(total, size=round(total * settings.DBA_SHARE), replace=False).tolist()
        )
        for i in range(total):
            while True:
                base = f"{self.pick(names.CARRIER_FIRST)} {self.pick(names.CARRIER_SECOND)}"
                if base not in used_names:
                    used_names.add(base)
                    break
            legal = f"{base} {self.pick(names.LEGAL_SUFFIXES)}"
            slug = base.lower().replace(" ", "")
            first_word = base.split()[0]
            dba = f"{first_word} {self.pick(names.DBA_WORDS)}" if i in dba_ids else None
            acct, routing = self.account()
            on_file = [f"billing@{slug}.example", f"dispatch@{slug}.example"]
            phone = f"555-01{int(self.rng.integers(10, 99))}-{int(self.rng.integers(1000, 9999))}"
            changed = settings.STREAM_START - timedelta(
                days=int(self.rng.integers(*settings.OLD_CHANGE_DAYS))
            )
            cid = f"C{i + 1:03d}"
            w.carriers.append(
                {
                    "id": cid,
                    "legal_name": legal,
                    "dba": dba,
                    "usdot": self.usdot(100_000, 500_000),
                    "contacts_on_file": on_file + [phone],
                    "home_factor": self.pick(settings.FACTORS)[0],
                    "dedicated": i >= settings.GENERAL_CARRIERS,
                    "remit_history": [
                        {
                            "account": acct,
                            "routing": routing,
                            "changed_at": iso(changed),
                            "verified": True,
                            "requested_via": on_file[0],
                        }
                    ],
                }
            )
            self.next_invoice[cid] = int(self.rng.integers(1000, 8000))

        used_b: set[str] = set()
        for i in range(settings.BROKERS):
            while True:
                bname = f"{self.pick(names.BROKER_FIRST)} {self.pick(names.BROKER_SECOND)}"
                if bname not in used_b:
                    used_b.add(bname)
                    break
            w.brokers.append(
                {"id": f"B{i + 1:02d}", "name": f"{bname} LLC", "usdot": self.usdot(500_000, 700_000)}
            )
        w.index()
        return w

    def general_carriers(self, w: World) -> list[dict]:
        return [c for c in w.carriers if not c["dedicated"]]

    def make_load(self, w: World, carrier_id: str, delivered: date, accessorial: bool) -> Load:
        broker = self.pick(w.brokers)
        items = [LineItem("Linehaul", self.money(900, 4500))]
        if accessorial:
            items.append(LineItem(self.pick(names.ACCESSORIALS), self.money(75, 400)))
        return Load(
            broker_id=broker["id"],
            carrier_id=carrier_id,
            load_no=self.load_no(),
            bol_no=self.bol_no(),
            pro_no=f"{int(self.rng.integers(100000, 999999))}" if self.chance(0.5) else None,
            origin=self.city(),
            dest=self.city(),
            pickup=delivered - timedelta(days=int(self.rng.integers(1, 4))),
            delivered=delivered,
            shipper=f"{self.pick(names.SHIPPER_FIRST)} {self.pick(names.SHIPPER_SECOND)}",
            consignee=f"{self.pick(names.SHIPPER_FIRST)} {self.pick(names.SHIPPER_SECOND)}",
            pieces=int(self.rng.integers(1, 30)),
            weight_lb=int(self.rng.integers(80, 440)) * 100,
            received_by=self.person(),
            items=items,
        )

    def build_history(self, w: World, n_paid: int, n_rejected: int) -> None:
        """Pre-stream paid and rejected requests, in time order, each through the carrier's factor."""
        total = n_paid + n_rejected
        minutes = np.sort(self.rng.integers(0, settings.HISTORY_DAYS * 24 * 60, size=total))
        kinds = np.array([True] * n_paid + [False] * n_rejected)
        self.rng.shuffle(kinds)
        start = settings.STREAM_START - timedelta(days=settings.HISTORY_DAYS)
        pool = self.general_carriers(w)
        for i, (m, is_paid) in enumerate(zip(minutes, kinds)):
            at = start + timedelta(minutes=int(m))
            carrier = self.pick(pool)
            delivered = (at - timedelta(days=int(self.rng.integers(0, 3)))).date()
            load = self.make_load(w, carrier["id"], delivered, self.chance(0.2))
            rid = f"H{self.seed}-{i + 1:04d}"
            self.history_loads[rid] = load
            broker = w.broker(load.broker_id)
            rec = {
                "request_id": rid,
                "factor_id": carrier["home_factor"],
                "broker_usdot": broker["usdot"],
                "load_no": load.load_no,
                "carrier_usdot": carrier["usdot"],
                "invoice_no": self.take_invoice_no(carrier["id"]),
                "amount_cents": sum(it.cents for it in load.items),
                "at": iso(at),
            }
            if is_paid:
                w.paid_loads.append(rec)
            else:
                rec["reason"] = self.pick(["missing POD signature", "invoice over rate con total"])
                w.rejected_requests.append(rec)

    # ---- documents -----------------------------------------------------------------------

    def layout(self) -> str:
        return self.pick(["A", "B"])

    def date_style(self) -> str:
        return self.pick(["iso", "month"])

    def ratecon_doc(self, w: World, load: Load) -> dict:
        broker = w.broker(load.broker_id)
        carrier = w.carrier(load.carrier_id)
        return {
            "layout": self.layout(),
            "date_style": self.date_style(),
            "broker_name": broker["name"],
            "broker_usdot": broker["usdot"],
            "load_no": load.load_no,
            "revision": load.revision,
            "carrier_name": carrier["legal_name"],
            "carrier_usdot": carrier["usdot"],
            "origin": load.origin,
            "pickup_date": load.pickup.isoformat(),
            "dest": load.dest,
            "delivery_date": load.delivered.isoformat(),
            "items": [asdict(it) for it in load.items],
        }

    def bol_doc(self, w: World, load: Load, hauler: dict | None = None) -> dict:
        """`hauler` overrides the carrier printed on the BOL (double brokering)."""
        carrier = hauler or w.carrier(load.carrier_id)
        return {
            "layout": self.layout(),
            "date_style": self.date_style(),
            "bol_no": load.bol_no,
            "load_no": load.load_no,
            "carrier_name": carrier["legal_name"],  # legal name only, never the DBA
            "carrier_usdot": carrier["usdot"],
            "pro_no": load.pro_no,
            "shipper": load.shipper,
            "consignee": load.consignee,
            "origin": load.origin,
            "dest": load.dest,
            "pieces": load.pieces,
            "weight_lb": load.weight_lb,
            "delivered_date": load.delivered.isoformat(),
            "received_by": load.received_by,
        }

    def invoice_doc(
        self, w: World, load: Load, invoice_no: str, invoice_date: date, items: list[LineItem], remit: dict
    ) -> dict:
        carrier = w.carrier(load.carrier_id)
        broker = w.broker(load.broker_id)
        return {
            "layout": self.layout(),
            "date_style": self.date_style(),
            "carrier_name": carrier["legal_name"],
            "carrier_usdot": carrier["usdot"],
            "invoice_no": invoice_no,
            "invoice_date": invoice_date.isoformat(),
            "bill_to": broker["name"],
            "load_no": load.load_no,
            "bol_no": load.bol_no,
            "items": [asdict(it) for it in items],
            "remit_account": remit["account"],
            "remit_routing": remit["routing"],
        }

    # ---- stream --------------------------------------------------------------------------

    def plan(self) -> tuple[list[tuple[str, object]], dict[int, int]]:
        """Slot labels in arrival order, plus the anchor position of each type-3 follower."""
        n = self.n
        labels: list[tuple[str, object]] = []
        for t, rate in settings.ISSUE_RATES.items():
            labels += [("issue", t)] * round(n * rate)
        for k, rate in settings.LOOKALIKE_RATES.items():
            labels += [("look", k)] * round(n * rate)
        if len(labels) > n:
            raise ValueError(f"N={n} is too small for the configured rates")
        labels += [("plain", None)] * (n - len(labels))
        order = self.rng.permutation(n)
        labels = [labels[i] for i in order]

        anchors: dict[int, int] = {}
        used: set[int] = set()
        p = 0
        while p < n:
            if labels[p] == ("issue", 3):
                lo = max(0, p - settings.ANCHOR_WINDOW)
                cands = [q for q in range(lo, p) if labels[q] == ("plain", None) and q not in used]
                if not cands:
                    # Nothing earlier to anchor on: move this follower to the next plain slot.
                    q = next(q for q in range(p + 1, n) if labels[q] == ("plain", None))
                    labels[p], labels[q] = labels[q], labels[p]
                    continue
                a = cands[int(self.rng.integers(len(cands)))]
                used.add(a)
                anchors[p] = a
            p += 1
        return labels, anchors

    def build(self) -> tuple[World, list[Packet]]:
        labels, anchors = self.plan()
        dedicated = sum(1 for lab in labels if lab in (("issue", 4), ("look", "bank_verified")))
        w = self.build_world(dedicated)

        n_rebill = sum(1 for lab in labels if lab == ("issue", 2))
        n_rej = sum(1 for lab in labels if lab == ("look", "rejected_rebill"))
        self.build_history(
            w, max(settings.PRE_STREAM_PAID, 2 * n_rebill), max(settings.PRE_STREAM_REJECTED, 2 * n_rej)
        )
        paid_pool = list(self.rng.permutation(len(w.paid_loads))[:n_rebill])
        rej_pool = list(self.rng.permutation(len(w.rejected_requests))[:n_rej])
        dedicated_pool = [c for c in w.carriers if c["dedicated"]]
        general = self.general_carriers(w)

        packets: list[Packet] = []
        at = settings.STREAM_START
        for seq, (kind, val) in enumerate(labels):
            at = at + timedelta(minutes=int(self.rng.integers(*settings.MINUTES_BETWEEN_REQUESTS)))
            rid = f"S{self.seed}-{seq + 1:04d}"

            if (kind, val) == ("issue", 3):
                anchor = packets[anchors[seq]]
                factor = self.pick([f for f, _ in settings.FACTORS if f != anchor.factor_id])
                docs = copy.deepcopy(anchor.docs)  # the same three PDFs, sent to a second factor
                total = sum(it["cents"] for it in docs.invoice["items"])
                packets.append(Packet(rid, seq, factor, at, 3, total, None, anchor.request_id, docs))
                continue

            delivered = (at - timedelta(days=int(self.rng.integers(0, 4)))).date()
            invoice_date = min(delivered + timedelta(days=int(self.rng.integers(0, 2))), at.date())

            if (kind, val) == ("issue", 2):
                rec = w.paid_loads[int(paid_pool.pop())]
                load = self.history_loads[rec["request_id"]]
                carrier = w.carrier(load.carrier_id)
                invoice_no = self.take_invoice_no(carrier["id"])
            elif (kind, val) == ("look", "rejected_rebill"):
                rec = w.rejected_requests[int(rej_pool.pop())]
                load = self.history_loads[rec["request_id"]]
                carrier = w.carrier(load.carrier_id)
                invoice_no = rec["invoice_no"]  # corrected re-bill keeps the invoice number
            else:
                if (kind, val) in (("issue", 4), ("look", "bank_verified")):
                    carrier = dedicated_pool.pop()
                else:
                    carrier = self.pick(general)
                accessorial = self.chance(settings.SHARE_WITH_AGREED_ACCESSORIAL)
                load = self.make_load(w, carrier["id"], delivered, accessorial and val != "ratecon_revision")
                invoice_no = self.take_invoice_no(carrier["id"])

            if val == "ratecon_revision":
                load.items.append(LineItem("Detention", self.money(75, 300)))
                load.revision = 2

            factor = carrier["home_factor"]
            if (kind, val) in (("issue", 4), ("look", "bank_verified")):
                self.add_remit_change(carrier, at, verified=(val == "bank_verified"))
            remit = carrier["remit_history"][-1]

            items = [copy.copy(it) for it in load.items]
            exposure = 0
            issue = val if kind == "issue" else 0
            if issue == 1:
                on_rc = {it.desc for it in items}
                extra = self.pick([a for a in names.ACCESSORIALS if a not in on_rc])
                pad = LineItem(extra, self.money(100, 450))
                items.append(pad)
                exposure = pad.cents

            hauler = None
            if issue == 5:
                hauler = self.other_hauler(w, carrier)

            docs = Docs(
                ratecon=self.ratecon_doc(w, load),
                bol=self.bol_doc(w, load, hauler),
                invoice=self.invoice_doc(w, load, invoice_no, invoice_date, items, remit),
            )
            total = sum(it.cents for it in items)
            if issue in (2, 4, 5):
                exposure = total
            look = val if kind == "look" else None
            packets.append(Packet(rid, seq, factor, at, issue, exposure, look, None, docs))
        return w, packets

    def add_remit_change(self, carrier: dict, at: datetime, verified: bool) -> None:
        acct, routing = self.account()
        when = at - timedelta(days=int(self.rng.integers(*settings.RECENT_CHANGE_DAYS)), minutes=int(self.rng.integers(0, 600)))
        if verified:
            via = self.pick(carrier["contacts_on_file"])
        else:
            slug = carrier["contacts_on_file"][0].split("@")[1].removesuffix(".example")
            via = f"accounts@{slug}-pay.example"
        carrier["remit_history"].append(
            {"account": acct, "routing": routing, "changed_at": iso(when), "verified": verified, "requested_via": via}
        )

    def other_hauler(self, w: World, carrier: dict) -> dict:
        """The carrier that actually shows up on the BOL: another registered carrier or an unknown one."""
        if self.chance(0.5):
            while True:
                c = self.pick(self.general_carriers(w))
                if c["id"] != carrier["id"]:
                    return c
        base = f"{self.pick(names.CARRIER_FIRST)} {self.pick(names.CARRIER_SECOND)}"
        return {"legal_name": f"{base} {self.pick(names.LEGAL_SUFFIXES)}", "usdot": self.usdot(700_000, 999_999)}


def build(seed: int, n: int) -> tuple[World, list[Packet]]:
    return Builder(seed, n).build()
