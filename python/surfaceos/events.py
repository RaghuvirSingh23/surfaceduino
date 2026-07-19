from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class InteractionEvent:
    sequence: int
    source: str
    kind: str
    control_id: str | None
    value: float | int | bool | str | None
    timestamp_ms: int
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = "surfaceos.event.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
