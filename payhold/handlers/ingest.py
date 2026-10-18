"""ingest(event, context): extract the packet's PDFs and record the request in seen_loads."""

from __future__ import annotations

from pathlib import Path

from payhold.extract.pdf import extract_packet
from payhold.handlers import runtime


def handler(event: dict, context=None) -> dict:
    packet = extract_packet(event["request"], Path(event["base_dir"]))
    runtime.get().ingest(packet)
    return {"packet": packet.model_dump(mode="json")}
