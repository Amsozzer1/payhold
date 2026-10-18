from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from payhold.checks.base import Reason


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    decision: Literal["pay", "hold"]
    reasons: tuple[Reason, ...] = ()
