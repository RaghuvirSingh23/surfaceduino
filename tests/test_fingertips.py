import unittest

import cv2
import numpy as np

from surfaceos.fingertips import FingertipParams, FingertipTracker


def _hand_mask(width: int = 320, height: int = 240) -> np.ndarray:
    """Synthetic hand: a palm block with three raised finger prongs."""
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.rectangle(mask, (120, 150), (200, 220), 255, -1)  # palm
    cv2.rectangle(mask, (130, 60), (145, 155), 255, -1)   # finger 1
    cv2.rectangle(mask, (155, 40), (170, 155), 255, -1)   # finger 2 (tallest)
    cv2.rectangle(mask, (180, 70), (195, 155), 255, -1)   # finger 3
    return mask


class FingertipTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = FingertipTracker(FingertipParams())

    def test_detects_multiple_finger_prongs(self):
        tips = self.tracker.detect(_hand_mask())
        self.assertGreaterEqual(len(tips), 3)
        for tip in tips:
            self.assertTrue(0.0 <= tip.x <= 1.0)
            self.assertTrue(0.0 <= tip.y <= 1.0)

    def test_topmost_tip_matches_tallest_finger(self):
        tips = self.tracker.detect(_hand_mask())
        highest = min(tips, key=lambda tip: tip.y)
        self.assertAlmostEqual(highest.x, 162.5 / 320, delta=0.06)
        self.assertLess(highest.y, 60 / 240)

    def test_empty_mask_returns_no_tips(self):
        empty = np.zeros((240, 320), dtype=np.uint8)
        self.assertEqual(self.tracker.detect(empty), [])


if __name__ == "__main__":
    unittest.main()
