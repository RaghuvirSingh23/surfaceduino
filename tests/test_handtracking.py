import math
import unittest
from pathlib import Path

import numpy as np

from surfaceos import handtracking as ht

ROOT = Path(__file__).resolve().parents[1]
PALM_MODEL = ROOT / "models" / "palm_detection_full.tflite"
LANDMARK_MODEL = ROOT / "models" / "hand_landmark_full.tflite"


class AnchorTests(unittest.TestCase):
    def test_anchor_count_matches_blazepalm_192(self):
        anchors = ht.generate_anchors()
        # 24x24x2 (stride 8) + 12x12x6 (stride 16) = 2016 anchors.
        self.assertEqual(anchors.shape, (2016, 4))

    def test_anchor_centers_are_normalized(self):
        anchors = ht.generate_anchors()
        self.assertTrue(np.all(anchors[:, 0] >= 0.0) and np.all(anchors[:, 0] <= 1.0))
        self.assertTrue(np.all(anchors[:, 1] >= 0.0) and np.all(anchors[:, 1] <= 1.0))
        # fixed_anchor_size -> width/height are 1.0
        self.assertTrue(np.allclose(anchors[:, 2:4], 1.0))


class GeometryTests(unittest.TestCase):
    def test_sigmoid_midpoint(self):
        self.assertAlmostEqual(float(ht._sigmoid(np.array([0.0]))[0]), 0.5)

    def test_normalize_radians_wraps_into_range(self):
        for angle in (-4 * math.pi, -math.pi, 0.0, math.pi, 3 * math.pi):
            wrapped = ht._normalize_radians(angle)
            self.assertGreaterEqual(wrapped, -math.pi - 1e-6)
            self.assertLessEqual(wrapped, math.pi + 1e-6)

    def test_rotated_rect_points_no_rotation(self):
        pts = ht._rotated_rect_points(10.0, 10.0, 4.0, 0.0)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self.assertAlmostEqual(min(xs), 8.0, places=5)
        self.assertAlmostEqual(max(xs), 12.0, places=5)
        self.assertAlmostEqual(min(ys), 8.0, places=5)
        self.assertAlmostEqual(max(ys), 12.0, places=5)

    def test_decode_rejects_low_scores(self):
        anchors = ht.generate_anchors()
        scores = np.full((anchors.shape[0], 1), -10.0, dtype=np.float32)  # sigmoid ~ 0
        boxes = np.zeros((anchors.shape[0], 18), dtype=np.float32)
        self.assertEqual(ht._decode_palms(scores, boxes, anchors, 0.5), [])

    def test_decode_accepts_high_score_box(self):
        anchors = ht.generate_anchors()
        scores = np.full((anchors.shape[0], 1), -10.0, dtype=np.float32)
        scores[0, 0] = 10.0  # sigmoid ~ 1
        boxes = np.zeros((anchors.shape[0], 18), dtype=np.float32)
        boxes[0, 2] = 40.0  # width in input pixels
        boxes[0, 3] = 40.0  # height in input pixels
        regions = ht._decode_palms(scores, boxes, anchors, 0.5)
        self.assertEqual(len(regions), 1)
        self.assertGreater(regions[0].box[2], 0.0)
        self.assertGreater(regions[0].box[3], 0.0)

    def test_nms_collapses_duplicates(self):
        a = ht._Region(score=0.9, box=np.array([0.1, 0.1, 0.2, 0.2], dtype=np.float32))
        b = ht._Region(score=0.8, box=np.array([0.11, 0.11, 0.2, 0.2], dtype=np.float32))
        c = ht._Region(score=0.7, box=np.array([0.7, 0.7, 0.2, 0.2], dtype=np.float32))
        kept = ht._nms([a, b, c], 0.3)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0].score, 0.9)


@unittest.skipUnless(
    ht._Interpreter is not None and PALM_MODEL.exists() and LANDMARK_MODEL.exists(),
    "LiteRT and hand models required",
)
class ModelSmokeTests(unittest.TestCase):
    def test_blank_frame_yields_no_hands(self):
        tracker = ht.HandLandmarker(PALM_MODEL, LANDMARK_MODEL)
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        self.assertEqual(tracker.process(frame), [])


if __name__ == "__main__":
    unittest.main()
