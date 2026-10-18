from payhold.baseline import Baseline
from payhold.engine import Payhold
from tests import factories as fx


def codes(decision):
    return [r.code for r in decision.reasons]


def run(ph, *packets):
    return [ph.process(p) for p in packets]


# ---- one pass and one fail case per check ------------------------------------------------


def test_clean_packet_pays():
    assert Payhold.from_world(fx.world()).process(fx.packet()).decision == "pay"


def test_padding():
    ph = Payhold.from_world(fx.world())
    d = ph.process(fx.packet(inv_items=(("Linehaul", 185000), ("Lumper", 17500))))
    assert codes(d) == ["padding"]
    assert "Lumper $175.00 not on rate con" in d.reasons[0].message


def test_padding_passes_agreed_accessorial():
    agreed = (("Linehaul", 185000), ("Detention", 15000))
    assert Payhold.from_world(fx.world()).process(fx.packet(rc_items=agreed)).decision == "pay"


def paid(load_no="4820157", invoice_no="1000", factor="F1", rid="H-1"):
    return {"request_id": rid, "factor_id": factor, "broker_usdot": "99500001", "load_no": load_no,
            "carrier_usdot": "99100001", "invoice_no": invoice_no, "amount_cents": 185000, "at": "2026-02-01T00:00:00Z"}


def test_rebill_same_factor_is_held():
    ph = Payhold.from_world(fx.world(paid_loads=[paid()]))
    d = ph.process(fx.packet(invoice_no="1044"))
    assert codes(d) == ["duplicate_rebill"]


def test_rebill_check_passes_fresh_load():
    ph = Payhold.from_world(fx.world(paid_loads=[paid(load_no="1111111")]))
    assert ph.process(fx.packet()).decision == "pay"


def test_double_factoring_second_factor_is_held():
    ph = Payhold.from_world(fx.world())
    first, second = run(ph, fx.packet("R1", "F1"), fx.packet("R2", "F2", requested_at="2026-03-02T10:45:00Z"))
    assert first.decision == "pay"
    assert codes(second) == ["double_factoring"]
    assert second.reasons[0].message == (
        "load 4820157 from broker USDOT 99500001 already requested through Alder Funding at 2026-03-02T10:00:00Z (request R1)"
    )


def test_double_factoring_first_request_held_then_second_factor_held():
    ph = Payhold.from_world(fx.world())
    padded = fx.packet("R1", "F1", inv_items=(("Linehaul", 185000), ("Lumper", 17500)))
    first, second = run(ph, padded, fx.packet("R2", "F2", requested_at="2026-03-02T10:45:00Z"))
    assert first.decision == "hold"
    assert "double_factoring" in codes(second)


def test_same_factor_after_rejection_passes():
    rej = dict(paid(invoice_no="1043"), reason="missing POD signature")
    ph = Payhold.from_world(fx.world(rejected_requests=[rej]))
    assert ph.process(fx.packet("R2", "F1")).decision == "pay"


def test_other_factor_rejection_still_counts_as_seen():
    rej = dict(paid(invoice_no="1043", factor="F2"), reason="missing POD signature")
    ph = Payhold.from_world(fx.world(rejected_requests=[rej]))
    assert codes(ph.process(fx.packet("R2", "F1"))) == ["double_factoring"]


def recent_change(verified: bool, via: str) -> dict:
    w = fx.world()
    w["carriers"][0]["remit_history"].append(
        {"account": "880099998888", "routing": "000999888", "changed_at": "2026-02-28T09:00:00Z", "verified": verified, "requested_via": via}
    )
    return w


def test_bank_change_unverified_unknown_contact_is_held():
    ph = Payhold.from_world(recent_change(False, "accounts@redbirdfreight-pay.example"))
    d = ph.process(fx.packet(remit=("880099998888", "000999888")))
    assert codes(d) == ["bank_change"]


def test_bank_check_passes_old_verified_account():
    assert Payhold.from_world(fx.world()).process(fx.packet()).decision == "pay"


def test_remit_not_on_file_is_held():
    d = Payhold.from_world(fx.world()).process(fx.packet(remit=("880000000000", "000111222")))
    assert codes(d) == ["remit_mismatch"]


def test_double_brokering_usdot_is_held():
    d = Payhold.from_world(fx.world()).process(fx.packet(bol_carrier_usdot="99700001", bol_carrier_name="Falcon Lines Inc"))
    assert codes(d) == ["double_brokering"]


def test_double_brokering_name_is_held():
    d = Payhold.from_world(fx.world()).process(fx.packet(bol_carrier_name="Falcon Lines Inc"))
    assert codes(d) == ["double_brokering"]


def test_double_brokering_passes_formatting_and_suffix_differences():
    d = Payhold.from_world(fx.world()).process(fx.packet(bol_carrier_name="REDBIRD FREIGHT, L.L.C."))
    assert d.decision == "pay"


def test_pod_missing_is_held():
    d = Payhold.from_world(fx.world()).process(fx.packet(received_by=None))
    assert codes(d) == ["pod_missing"]


# ---- one test per seen look-alike kind ---------------------------------------------------


def test_lookalike_verified_recent_bank_change_pays():
    ph = Payhold.from_world(recent_change(True, "billing@redbirdfreight.example"))
    assert ph.process(fx.packet(remit=("880099998888", "000999888"))).decision == "pay"


def test_lookalike_rate_con_revision_with_detention_pays():
    rev = (("Linehaul", 185000), ("Detention", 22500))
    assert Payhold.from_world(fx.world()).process(fx.packet(rc_items=rev, inv_items=rev)).decision == "pay"


def test_lookalike_corrected_rebill_after_rejection_pays():
    rej = dict(paid(invoice_no="1043"), reason="invoice over rate con total")
    ph = Payhold.from_world(fx.world(rejected_requests=[rej]))
    assert ph.process(fx.packet("R9", "F1", invoice_no="1043")).decision == "pay"


# ---- baseline ----------------------------------------------------------------------------


def test_baseline_rejected_then_rebilled_pays():
    rej = dict(paid(invoice_no="1043"), reason="missing POD signature")
    bl = Baseline(fx.world(rejected_requests=[rej]))
    assert bl.process(fx.packet("R2", "F1")).decision == "pay"


def test_baseline_same_load_number_different_broker_pays():
    bl = Baseline(fx.world(paid_loads=[paid(invoice_no="999")]))
    assert bl.process(fx.packet(broker_usdot="99500002", invoice_no="1044")).decision == "pay"


def test_baseline_catches_padding_and_same_factor_rebill():
    bl = Baseline(fx.world(paid_loads=[paid()]))
    assert bl.process(fx.packet("R1", inv_items=(("Linehaul", 185000), ("Lumper", 17500)), load_no="7")).decision == "hold"
    assert bl.process(fx.packet("R2", invoice_no="1044")).decision == "hold"


def test_baseline_misses_second_factor_and_treats_pending_as_held():
    bl = Baseline(fx.world())
    assert bl.process(fx.packet("R1", "F1")).decision == "pay"
    assert bl.process(fx.packet("R2", "F2")).decision == "pay"  # the other factor's book is invisible
    padded = fx.packet("R3", "F1", load_no="5555555", invoice_no="2000", inv_items=(("Linehaul", 185000), ("Lumper", 1)))
    assert bl.process(padded).decision == "hold"
    assert bl.process(fx.packet("R4", "F1", load_no="5555555", invoice_no="2001")).decision == "hold"


# ---- snapshot ----------------------------------------------------------------------------


def test_deciding_against_snapshot_leaves_original_unchanged():
    ph = Payhold.from_world(fx.world())
    bl = Baseline(fx.world())
    for d in (ph, bl):
        d.process(fx.packet("R1", "F1"))
    before_seen = ph.store.seen(fx.packet().load_key)
    before_audit = ph.store.audit("R1")
    before_books = repr(bl.books)

    snap_ph, snap_bl = ph.snapshot(), bl.snapshot()
    probe = fx.packet("X1", "F2", requested_at="2026-03-03T00:00:00Z")
    assert snap_ph.process(probe).decision == "hold"
    snap_bl.process(probe)

    assert ph.store.seen(fx.packet().load_key) == before_seen
    assert ph.store.audit("R1") == before_audit and ph.store.audit("X1") == []
    assert ph.store.get_payout(probe.payout_key).request_id == "R1"
    assert repr(bl.books) == before_books
