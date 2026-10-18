"""Shared types for checks. Each check returns None or a Reason."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from payhold.config import Thresholds
from payhold.models import Packet
from payhold.registry import Registry
from payhold.store.base import Store


class FieldRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc: str
    field: str
    raw: str | None
    bbox: tuple[float, float, float, float] | None
    page: int = 0


class Reason(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    fields: tuple[FieldRef, ...] = ()


@dataclass
class Context:
    registry: Registry
    store: Store
    thresholds: Thresholds


def ref(packet: Packet, doc: str, field: str) -> FieldRef:
    f = getattr(getattr(packet, doc), field)
    return FieldRef(doc=doc, field=field, raw=f.raw, bbox=f.bbox, page=f.page)


def dollars(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"
