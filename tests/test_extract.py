import copy
import json

from eval.roundtrip import check_seed
from generator.render import render_bol, render_invoice, render_ratecon
from payhold.extract.layouts import BOL, INVOICE, RATECON
from payhold.extract.pdf import extract_doc
from payhold.models import load_key


def test_round_trip_every_field_seed1(seed1):
    checked, fails, details = check_seed(seed1)
    assert checked == 500 * 36
    assert not fails, details[:10]


def first_spec(seed1, doc):
    packets = json.loads((seed1 / "truth.json").read_text())["packets"]
    return packets[0]["docs"][doc]


def render_both(spec, render, layouts, tmp_path, name):
    out = {}
    for lay in ("A", "B"):
        s = copy.deepcopy(spec)
        s["layout"] = lay
        s["date_style"] = "iso" if lay == "A" else "month"
        path = tmp_path / f"{name}_{lay}.pdf"
        render(s, path)
        out[lay] = extract_doc(path, layouts)
        assert out[lay]["layout"] == lay
    return out


def test_load_key_is_layout_invariant(seed1, tmp_path):
    rc = render_both(first_spec(seed1, "ratecon"), render_ratecon, RATECON, tmp_path, "rc")
    keys = {lay: load_key(d["broker_usdot"].norm, d["load_no"].norm) for lay, d in rc.items()}
    assert keys["A"] == keys["B"]
    assert rc["A"]["load_no"].raw != rc["B"]["load_no"].raw  # printed differently, same key


def test_every_field_is_layout_invariant(seed1, tmp_path):
    for doc, render, layouts in (("ratecon", render_ratecon, RATECON), ("bol", render_bol, BOL), ("invoice", render_invoice, INVOICE)):
        both = render_both(first_spec(seed1, doc), render, layouts, tmp_path, doc)
        for field, a in both["A"].items():
            if field == "layout":
                continue
            b = both["B"][field]
            if field == "items":
                assert [(i.desc.norm, i.amount.norm) for i in a] == [(i.desc.norm, i.amount.norm) for i in b]
            else:
                assert a.norm == b.norm, (doc, field, a.raw, b.raw)
                if a.norm is not None:
                    assert a.bbox and b.bbox and a.page == 0
