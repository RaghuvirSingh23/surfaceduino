import unittest

import cv2
import numpy as np

from surfaceos.inputs.remote_frames import RemoteFrameInbox, decode_jpeg


def jpeg(width: int = 64, height: int = 48) -> bytes:
    frame = np.full((height, width, 3), 180, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("test JPEG encoding failed")
    return encoded.tobytes()


class RemoteFrameTests(unittest.TestCase):
    def test_latest_frame_replaces_pending_frame(self):
        inbox = RemoteFrameInbox(max_jpeg_bytes=100_000)
        first, replaced_first = inbox.put(jpeg(), 1000, host_sequence="1")
        second, replaced_second = inbox.put(jpeg(), 1020, host_sequence="2")

        packet = inbox.take_latest()
        self.assertEqual((first, second), (1, 2))
        self.assertFalse(replaced_first)
        self.assertTrue(replaced_second)
        self.assertEqual(packet.host_sequence, "2")
        self.assertIsNone(inbox.take_latest())

    def test_rejects_invalid_or_oversized_payload(self):
        inbox = RemoteFrameInbox(max_jpeg_bytes=10)
        with self.assertRaisesRegex(ValueError, "invalid JPEG"):
            inbox.put(b"not-a-jpeg", 1000)
        with self.assertRaisesRegex(ValueError, "too large"):
            inbox.put(b"\xff\xd8" + b"x" * 10 + b"\xff\xd9", 1000)

    def test_stats_report_age_backpressure_and_fps(self):
        inbox = RemoteFrameInbox(max_jpeg_bytes=100_000)
        inbox.put(jpeg(), 1000)
        inbox.put(jpeg(), 1100)
        stats = inbox.stats(1250)
        self.assertEqual(stats["accepted"], 2)
        self.assertEqual(stats["replaced"], 1)
        self.assertEqual(stats["age_ms"], 150)
        self.assertEqual(stats["fps"], 10.0)

    def test_decodes_jpeg_and_caps_resolution(self):
        frame = decode_jpeg(jpeg(64, 48), (128, 96))
        self.assertEqual(frame.shape, (48, 64, 3))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            decode_jpeg(jpeg(64, 48), (32, 24))


if __name__ == "__main__":
    unittest.main()
