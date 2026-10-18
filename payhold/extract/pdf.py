"""Label-anchored field extraction with pdfplumber. Rules-based, for system-generated PDFs only."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from payhold.extract import normalize as nz
from payhold.extract.layouts import BOL, INVOICE, NORMALIZERS, RATECON, Layout
from payhold.models import Bol, Field, Invoice, Item, Packet, RateCon

LINE_TOL = 2.0  # words whose tops are this close are on the same line
MAX_BODY_SIZE = 30  # anything bigger is the watermark


class ExtractionError(ValueError):
    pass


Word = dict


def read_lines(path: Path) -> list[list[Word]]:
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(extra_attrs=["size"])
    words = [w for w in words if w["upright"] and w["size"] < MAX_BODY_SIZE]
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines: list[list[Word]] = []
    for w in words:
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    for ln in lines:
        ln.sort(key=lambda w: w["x0"])
    return lines


def find_label(line: list[Word], label: str) -> tuple[int, int] | None:
    """Index range [i, j) of `label`'s words in `line`, if present."""
    toks = label.split()
    texts = [w["text"] for w in line]
    for i in range(len(texts) - len(toks) + 1):
        if texts[i : i + len(toks)] == toks:
            return i, i + len(toks)
    return None


def bbox(words: list[Word]) -> tuple[float, float, float, float] | None:
    if not words:
        return None
    return (
        round(min(w["x0"] for w in words), 2),
        round(min(w["top"] for w in words), 2),
        round(max(w["x1"] for w in words), 2),
        round(max(w["bottom"] for w in words), 2),
    )


def make_field(words: list[Word], normalize) -> Field:
    if not words:
        return Field()
    raw = " ".join(w["text"] for w in words)
    return Field(raw=raw, norm=normalize(raw), bbox=bbox(words), page=0)


def label_hits(lines: list[list[Word]], layout: Layout) -> dict[str, tuple[int, int, int]]:
    """field -> (line index, label start, label end) for each label found."""
    hits = {}
    for field, label in layout.labels.items():
        for li, line in enumerate(lines):
            r = find_label(line, label)
            if r:
                hits[field] = (li, *r)
                break
    return hits


def detect(lines: list[list[Word]], layouts: list[Layout]) -> tuple[Layout, dict]:
    best = None
    for lay in layouts:
        hits = label_hits(lines, lay)
        required = set(lay.labels) - lay.optional
        score = len(required & set(hits)) / len(required)
        if best is None or score > best[0]:
            best = (score, lay, hits)
    score, lay, hits = best
    if score < 0.8:
        raise ExtractionError(f"no known layout matches (best {lay.name} at {score:.0%})")
    return lay, hits


def values(lines: list[list[Word]], hits: dict) -> dict[str, list[Word]]:
    """Value of each label: the words after it on its line, up to the next label on that line."""
    by_line: dict[int, list[tuple[int, int, str]]] = {}
    for field, (li, i, j) in hits.items():
        by_line.setdefault(li, []).append((i, j, field))
    out = {}
    for li, spans in by_line.items():
        spans.sort()
        for k, (i, j, field) in enumerate(spans):
            end = spans[k + 1][0] if k + 1 < len(spans) else len(lines[li])
            out[field] = lines[li][j:end]
    return out


def table_items(lines: list[list[Word]], layout: Layout) -> tuple[Item, ...]:
    t = layout.table
    head = next((li for li, ln in enumerate(lines) if [w["text"] for w in ln] == list(t.header)), None)
    end = next((li for li, ln in enumerate(lines) if find_label(ln, t.total_label)), None)
    if head is None or end is None or end <= head:
        raise ExtractionError(f"charges table not found in layout {layout.name}")
    h = lines[head]
    split = (h[0]["x1"] + h[1]["x0"]) / 2
    items = []
    for ln in lines[head + 1 : end]:
        left = [w for w in ln if w["x0"] < split]
        right = [w for w in ln if w["x0"] >= split]
        amt, dsc = (left, right) if t.amount_col == 0 else (right, left)
        items.append(Item(desc=make_field(dsc, nz.desc), amount=make_field(amt, nz.money)))
    return tuple(items)


def extract_doc(path: Path, layouts: list[Layout]) -> dict:
    lines = read_lines(path)
    lay, hits = detect(lines, layouts)
    vals = values(lines, hits)
    out: dict = {"layout": lay.name}
    for field in lay.labels:
        out[field] = make_field(vals.get(field, []), NORMALIZERS[field])
    if lay.table:
        out["items"] = table_items(lines, lay)
    return out


def extract_packet(request: dict, base: Path) -> Packet:
    """`request` is one record of requests.json; doc paths are relative to `base`."""
    docs = request["docs"]
    return Packet(
        request_id=request["request_id"],
        factor_id=request["factor_id"],
        requested_at=request["requested_at"],
        ratecon=RateCon(**extract_doc(base / docs["ratecon"], RATECON)),
        bol=Bol(**extract_doc(base / docs["bol"], BOL)),
        invoice=Invoice(**extract_doc(base / docs["invoice"], INVOICE)),
    )
