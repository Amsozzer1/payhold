"""Normalizers for extracted text. Each takes raw text and returns a canonical value or None."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

LEGAL_SUFFIXES = {"LLC", "INC", "CO", "CORP", "LTD", "LP", "LLP", "COMPANY", "CORPORATION", "INCORPORATED"}


def money(raw: str | None) -> int | None:
    """'$1,850.00' or '1850.00 USD' -> 185000 (cents)."""
    if not raw:
        return None
    s = re.sub(r"[^0-9.\-]", "", raw)
    try:
        return int((Decimal(s) * 100).to_integral_value())
    except InvalidOperation:
        return None


def date(raw: str | None) -> str | None:
    """'2026-03-04' or 'Mar 4, 2026' -> '2026-03-04'."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def digits(raw: str | None) -> str | None:
    if not raw:
        return None
    d = re.sub(r"\D", "", raw)
    return d or None


def integer(raw: str | None) -> int | None:
    d = digits(raw)
    return int(d) if d else None


def ident(raw: str | None, prefixes: tuple[str, ...] = ()) -> str | None:
    """Load, BOL and invoice numbers: uppercase alphanumerics, known prefixes dropped."""
    if not raw:
        return None
    s = re.sub(r"[^0-9A-Z]", "", raw.upper())
    for p in prefixes:
        if s.startswith(p) and len(s) > len(p):
            s = s[len(p):]
            break
    return s or None


def load_no(raw: str | None) -> str | None:
    return ident(raw)


def bol_no(raw: str | None) -> str | None:
    return ident(raw, ("BOL", "BL"))


def invoice_no(raw: str | None) -> str | None:
    return ident(raw, ("INV",))


def name(raw: str | None) -> str | None:
    """'REDBIRD FREIGHT, L.L.C.' and 'Redbird Freight LLC' -> 'REDBIRD FREIGHT'."""
    if not raw:
        return None
    s = re.sub(r"[.,']", "", raw.upper())
    s = re.sub(r"[^A-Z0-9&]+", " ", s).split()
    while s and s[-1] in LEGAL_SUFFIXES:
        s.pop()
    return " ".join(s) or None


def desc(raw: str | None) -> str | None:
    """Charge descriptions: 'Stop-off' and 'STOP-OFF' -> 'STOPOFF'."""
    if not raw:
        return None
    return re.sub(r"[^A-Z0-9]", "", raw.upper()) or None


def text(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = " ".join(raw.split())
    return s or None
