"""Exports seed 1 for the money-shot page: the decision stream, the featured packet, and page PNGs.

PNGs are 100 dpi with boxes drawn over the fields behind each hold, for held packets only.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pdfplumber
from PIL import Image, ImageDraw

DPI = 100
SCALE = DPI / 72
BOX = (220, 38, 38)


def featured_row(rows):
    """The first type-3 follower the baseline paid and payhold held."""
    for row in rows:
        if row.truth["issue_type"] == 3 and row.baseline.decision == "pay" and row.payhold.decision == "hold":
            return row
    return None


def boxes_for(row) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = {"ratecon": [], "bol": [], "invoice": []}
    for reason in row.payhold.reasons:
        for f in reason.fields:
            if f.bbox:
                out[f.doc].append(f.bbox)
    if any(r.code == "double_factoring" for r in row.payhold.reasons):
        # The page shows where the load and BOL numbers sit on every document, not just the ones the check cites.
        p = row.packet
        for doc, field in (("ratecon", "load_no"), ("bol", "load_no"), ("bol", "bol_no"), ("invoice", "load_no"), ("invoice", "bol_no")):
            bb = getattr(getattr(p, doc), field).bbox
            if bb and bb not in out[doc]:
                out[doc].append(bb)
    return out


def render_png(pdf_path: Path, boxes: list[tuple], out: Path) -> None:
    with pdfplumber.open(pdf_path) as pdf:
        img = pdf.pages[0].to_image(resolution=DPI).original.convert("RGB")
    draw = ImageDraw.Draw(img)
    for x0, top, x1, bottom in boxes:
        draw.rectangle([x0 * SCALE - 4, top * SCALE - 4, x1 * SCALE + 4, bottom * SCALE + 4], outline=BOX, width=3)
    img = img.quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)


def export(run, seed_dir: Path, out: Path) -> dict:
    feat = featured_row(run.rows)
    assert feat is not None, "featured packet missing: no type-3 follower with baseline=pay and payhold=hold"
    if out.exists():
        shutil.rmtree(out)
    (out / "pages").mkdir(parents=True)
    factor_names = {f["id"]: f["name"] for f in run.world["factors"]}
    requests = {r["request_id"]: r for r in json.loads((seed_dir / "requests.json").read_text())}

    stream = []
    cum_b = cum_p = 0
    for row in run.rows:
        t = row.truth
        bad = bool(t["issue_type"])
        if bad and row.baseline.decision == "pay":
            cum_b += t["exposure_cents"]
        if bad and row.payhold.decision == "pay":
            cum_p += t["exposure_cents"]
        held = row.payhold.decision == "hold"
        stream.append(
            {
                "seq": t["seq"],
                "request_id": t["request_id"],
                "factor": factor_names[t["factor_id"]],
                "requested_at": requests[t["request_id"]]["requested_at"],
                "issue_type": t["issue_type"],
                "issue_name": t["issue_name"],
                "lookalike": t["lookalike"],
                "exposure_cents": t["exposure_cents"],
                "baseline": row.baseline.decision,
                "payhold": row.payhold.decision,
                "reasons": [r.message for r in row.payhold.reasons],
                "cum_baseline_cents": cum_b,
                "cum_payhold_cents": cum_p,
                "pages": held,
            }
        )
        if held:
            for doc, bxs in boxes_for(row).items():
                render_png(seed_dir / requests[t["request_id"]]["docs"][doc], bxs, out / "pages" / t["request_id"] / f"{doc}.png")

    anchor = next(r for r in run.rows if r.request_id == feat.truth["anchor_request_id"])
    reason = next(r for r in feat.payhold.reasons if r.code == "double_factoring")
    featured = {
        "request_id": feat.request_id,
        "seq": feat.truth["seq"],
        "factor": factor_names[feat.truth["factor_id"]],
        "requested_at": requests[feat.request_id]["requested_at"],
        "anchor_request_id": anchor.request_id,
        "anchor_factor": factor_names[anchor.truth["factor_id"]],
        "anchor_requested_at": requests[anchor.request_id]["requested_at"],
        "exposure_cents": feat.truth["exposure_cents"],
        "load_no": feat.packet.ratecon.load_no.raw,
        "bol_no": feat.packet.bol.bol_no.raw,
        "reason": reason.message,
        "baseline": feat.baseline.decision,
        "payhold": feat.payhold.decision,
    }
    clean = [s for s in stream if not s["issue_type"]]
    summary = {
        "seed": run.seed,
        "packets": len(stream),
        "clean_packets": len(clean),
        "clean_paid_baseline": sum(1 for s in clean if s["baseline"] == "pay"),
        "clean_paid_payhold": sum(1 for s in clean if s["payhold"] == "pay"),
        "bad_packets": len(stream) - len(clean),
        "exposure_planted_cents": sum(s["exposure_cents"] for s in stream),
        "exposure_paid_baseline_cents": cum_b,
        "exposure_paid_payhold_cents": cum_p,
    }
    data = {"synthetic": True, "summary": summary, "featured": featured, "stream": stream}
    (out / "seed1.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    return data
