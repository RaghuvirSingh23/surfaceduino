from __future__ import annotations

from dataclasses import dataclass

from .events import InteractionEvent


@dataclass(frozen=True)
class Selection:
    control_id: str
    confidence: float
    since_ms: int
    last_seen_ms: int


class FusionEngine:
    """Combines a visual selection with an explicit confirmation source.

    Button, dwell, Hall and future movement/tap inputs all call ``confirm``.
    Consumers only see the stable InteractionEvent schema.
    """

    def __init__(self, stable_ms: int, candidate_timeout_ms: int):
        self._stable_ms = stable_ms
        self._candidate_timeout_ms = candidate_timeout_ms
        self._selection: Selection | None = None
        self._sequence = 0

    @property
    def selection(self) -> Selection | None:
        return self._selection

    def update_selection(self, control_id: str | None, confidence: float, timestamp_ms: int) -> None:
        if control_id is None:
            self._selection = None
            return
        if self._selection is None or self._selection.control_id != control_id:
            self._selection = Selection(control_id, confidence, timestamp_ms, timestamp_ms)
            return
        self._selection = Selection(
            control_id=control_id,
            confidence=confidence,
            since_ms=self._selection.since_ms,
            last_seen_ms=timestamp_ms,
        )

    def clear_selection(self) -> None:
        self._selection = None

    def activate_direct(self, control_id: str, source: str, timestamp_ms: int) -> InteractionEvent:
        """Emit a normal activation for a control that is already unambiguous.

        This is used by the two-button fallback while the USB camera is absent.
        Keeping it in the fusion engine preserves one event sequence and the same
        public event contract for vision, buttons and future sensors.
        """
        self._sequence += 1
        return InteractionEvent(
            sequence=self._sequence,
            source=source,
            kind="control.activate",
            control_id=control_id,
            value=1,
            timestamp_ms=timestamp_ms,
            confidence=1.0,
            metadata={"input_mode": "direct_buttons"},
        )

    def confirm(self, source: str, timestamp_ms: int, confidence: float = 1.0) -> InteractionEvent:
        selection = self._selection
        stable = selection is not None and timestamp_ms - selection.since_ms >= self._stable_ms
        fresh = selection is not None and timestamp_ms - selection.last_seen_ms <= self._candidate_timeout_ms

        self._sequence += 1
        if not stable or not fresh:
            reason = "no_selection"
            if selection is not None and not stable:
                reason = "selection_not_stable"
            elif selection is not None and not fresh:
                reason = "selection_stale"
            return InteractionEvent(
                sequence=self._sequence,
                source=source,
                kind="control.rejected",
                control_id=selection.control_id if selection else None,
                value=0,
                timestamp_ms=timestamp_ms,
                confidence=0.0,
                metadata={"reason": reason},
            )

        combined_confidence = max(0.0, min(1.0, selection.confidence * confidence))
        return InteractionEvent(
            sequence=self._sequence,
            source=source,
            kind="control.activate",
            control_id=selection.control_id,
            value=1,
            timestamp_ms=timestamp_ms,
            confidence=combined_confidence,
            metadata={"selected_for_ms": timestamp_ms - selection.since_ms},
        )
