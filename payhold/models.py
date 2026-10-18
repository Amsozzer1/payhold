"""Typed packet: what extraction produces and what both deciders read."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict

Norm = str | int | None


class Field(BaseModel):
    """One extracted value: raw text, normalized value, bounding box in PDF points (top-left origin), page."""

    model_config = ConfigDict(frozen=True)

    raw: str | None = None
    norm: Norm = None
    bbox: tuple[float, float, float, float] | None = None
    page: int = 0


class Item(BaseModel):
    model_config = ConfigDict(frozen=True)

    desc: Field
    amount: Field


class RateCon(BaseModel):
    model_config = ConfigDict(frozen=True)

    layout: str
    broker_name: Field
    broker_usdot: Field
    load_no: Field
    revision: Field
    carrier_name: Field
    carrier_usdot: Field
    origin: Field
    pickup_date: Field
    dest: Field
    delivery_date: Field
    items: tuple[Item, ...]
    total: Field


class Bol(BaseModel):
    model_config = ConfigDict(frozen=True)

    layout: str
    bol_no: Field
    load_no: Field
    carrier_name: Field
    carrier_usdot: Field
    pro_no: Field
    shipper: Field
    consignee: Field
    origin: Field
    dest: Field
    pieces: Field
    weight_lb: Field
    delivered_date: Field
    received_by: Field


class Invoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    layout: str
    carrier_name: Field
    carrier_usdot: Field
    invoice_no: Field
    invoice_date: Field
    bill_to: Field
    load_no: Field
    bol_no: Field
    items: tuple[Item, ...]
    total: Field
    remit_account: Field
    remit_routing: Field


class Packet(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    factor_id: str
    requested_at: str  # ISO 8601 UTC, from the synthetic clock
    ratecon: RateCon
    bol: Bol
    invoice: Invoice

    @property
    def load_key(self) -> str:
        return load_key(self.ratecon.broker_usdot.norm, self.ratecon.load_no.norm)

    @property
    def payout_key(self) -> str:
        return f"{self.load_key}#linehaul"


def load_key(broker_usdot: Norm, load_no: Norm) -> str:
    """sha256(norm(broker_usdot) | norm(broker_load_no)), built only from rate con fields."""
    return hashlib.sha256(f"{broker_usdot}|{load_no}".encode()).hexdigest()
