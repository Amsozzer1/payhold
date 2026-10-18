"""Shared state for the Lambda-shaped handlers: one Payhold per process, built from env on first use."""

from __future__ import annotations

import json
import os
from pathlib import Path

from payhold.engine import Payhold

_runtime: Payhold | None = None


def get() -> Payhold:
    global _runtime
    if _runtime is None:
        world = json.loads(Path(os.environ["PAYHOLD_WORLD"]).read_text())
        store = None
        if os.environ.get("PAYHOLD_STORE") == "dynamodb":
            from payhold.store.dynamo import DynamoStore

            store = DynamoStore.from_env()
        _runtime = Payhold.from_world(world, store)
    return _runtime


def set(ph: Payhold | None) -> None:
    global _runtime
    _runtime = ph
