import dataclasses
import unittest
from pathlib import Path

import cv2
import numpy as np

from surfaceos.config import load_config
from surfaceos.detector import BackgroundZoneDetector


ROOT = Path(__file__).resolve().parents[1]


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "config" / "surface.json")
        # These tests simulate solid blobs (not real hands), so exercise the
        # marker-free convexity fingertip path deterministically.
        detector_config = dataclasses.replace(self.config.detector, method="fingertip")
        self.detector = BackgroundZoneDetector(
            detector_config,
            self.config.zones,
            self.config.camera.processing_resolution,
        )
        self.empty = np.full((480, 640, 3), 210, dtype=np.uint8)
        self.detector.analyze(self.empty)

    def occupied_frame(self, zone_index: int) -> np.ndarray:
        frame = self.empty.copy()
        zone = self.config.zones[zone_index]
        x0, y0, x1, y1 = zone.rect
        cv2.rectangle(
            frame,
            (round(x0 * 640) + 10, round(y0 * 480) + 10),
            (round(x1 * 640) - 10, round(y1 * 480) - 10),
            (20, 20, 20),
            -1,
        )
        return frame

    def test_press_selects_first_piano_key(self):
        snapshot = None
        for _ in range(self.config.detector.press_frames):
            snapshot = self.detector.analyze(self.occupied_frame(0))
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.candidate_id, "piano_c4")
        self.assertFalse(snapshot.ambiguous)

    def test_two_zones_are_reported_as_ambiguous_by_detector(self):
        frame = self.occupied_frame(0)
        right = self.occupied_frame(1)
        frame[right[:, :, 0] < 100] = (20, 20, 20)
        snapshot = None
        for _ in range(self.config.detector.press_frames):
            snapshot = self.detector.analyze(frame)
        self.assertIsNone(snapshot.candidate_id)
        self.assertTrue(snapshot.ambiguous)

    def test_release_hysteresis_clears_candidate(self):
        for _ in range(self.config.detector.press_frames):
            self.detector.analyze(self.occupied_frame(0))
        snapshot = None
        for _ in range(self.config.detector.release_frames):
            snapshot = self.detector.analyze(self.empty)
        self.assertIsNone(snapshot.candidate_id)


if __name__ == "__main__":
    unittest.main()
