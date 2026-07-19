from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MovementConfirmationAdapter:
    """Disabled-by-default seam for the future Modulino Movement sensor.

    The MCU will eventually send impact magnitude and time over RouterBridge. This
    adapter decides whether that impact is strong enough to call FusionEngine.confirm.
    """

    enabled: bool = False
    impact_threshold_g: float = 1.5

    def accepts(self, magnitude_g: float) -> bool:
        return self.enabled and magnitude_g >= self.impact_threshold_g
