import json
import tempfile
import unittest
from pathlib import Path

from surfaceos.config import load_config


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_repository_config_loads(self):
        config = load_config(ROOT / "config" / "surface.json")
        self.assertEqual(config.camera.transport, "http_push")
        self.assertEqual(config.camera.resolution, (640, 480))
        self.assertEqual(config.camera.max_resolution, (1280, 720))
        self.assertEqual(len(config.zones), 10)
        self.assertEqual(config.activation_mode, "vision_press")
        self.assertEqual([zone.group for zone in config.zones].count("piano"), 6)
        self.assertEqual([zone.group for zone in config.zones].count("drum"), 4)
        self.assertEqual(config.zones[0].id, "piano_c4")

    def test_rejects_overlapping_hysteresis_thresholds(self):
        raw = json.loads((ROOT / "config" / "surface.json").read_text())
        raw["detector"]["release_ratio"] = raw["detector"]["press_ratio"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "release_ratio"):
                load_config(path)

    def test_rejects_unknown_camera_transport(self):
        raw = json.loads((ROOT / "config" / "surface.json").read_text())
        raw["camera"]["transport"] = "telepathy"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "camera.transport"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
