import unittest

from surfaceos.fusion import FusionEngine


class FusionTests(unittest.TestCase):
    def test_confirm_requires_a_stable_selection(self):
        engine = FusionEngine(stable_ms=180, candidate_timeout_ms=350)
        engine.update_selection("zone_left", 0.9, 1000)
        event = engine.confirm("mcu.button", 1100)
        self.assertEqual(event.kind, "control.rejected")
        self.assertEqual(event.metadata["reason"], "selection_not_stable")

    def test_stable_selection_activates(self):
        engine = FusionEngine(stable_ms=180, candidate_timeout_ms=350)
        engine.update_selection("zone_right", 0.8, 1000)
        engine.update_selection("zone_right", 0.9, 1200)
        event = engine.confirm("mcu.button", 1220)
        self.assertEqual(event.kind, "control.activate")
        self.assertEqual(event.control_id, "zone_right")
        self.assertAlmostEqual(event.confidence, 0.9)

    def test_stale_selection_is_rejected(self):
        engine = FusionEngine(stable_ms=10, candidate_timeout_ms=100)
        engine.update_selection("zone_left", 1.0, 1000)
        event = engine.confirm("movement.impact", 1200)
        self.assertEqual(event.kind, "control.rejected")
        self.assertEqual(event.metadata["reason"], "selection_stale")

    def test_direct_button_activates_without_visual_selection(self):
        engine = FusionEngine(stable_ms=180, candidate_timeout_ms=350)
        event = engine.activate_direct("zone_left", "mcu.button", 1200)
        self.assertEqual(event.kind, "control.activate")
        self.assertEqual(event.control_id, "zone_left")
        self.assertEqual(event.metadata["input_mode"], "direct_buttons")


if __name__ == "__main__":
    unittest.main()
