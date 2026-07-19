"""MediaPipe-grade hand landmark tracking via LiteRT.

This runs Google's own BlazePalm palm-detection model and the 21-point hand
landmark model (the exact networks behind MediaPipe Hands) through the
``ai-edge-litert`` runtime, which ships wheels for the UNO Q's Python 3.13 /
aarch64 Debian side. It is a pure detect -> track pipeline with no MediaPipe
dependency, so the same module runs on a laptop and on the board.

Pipeline (per the MediaPipe hand graph):

1. Pad the frame to a square, feed 192x192 to palm detection.
2. Decode the 2016 SSD anchors into palm boxes + 7 keypoints, run NMS.
3. Turn each palm into a rotated, wrist-aligned ROI expanded 2.9x.
4. Warp the ROI to 224x224 and run the landmark model -> 21 (x, y, z) points.
5. Reuse the landmark-derived ROI on the next frame (tracking) and only fall
   back to palm detection when a hand is lost or periodically to find new ones.

Reference for the anchor options, decode math and ROI geometry:
https://github.com/geaxgx/depthai_hand_tracker (Apache-2.0), which targets the
same ``palm_detection_full`` / ``hand_landmark_full`` tflite models used here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

try:  # LiteRT is only present on the deployed board / dev machines with the dep.
    from ai_edge_litert.interpreter import Interpreter as _Interpreter
except Exception:  # pragma: no cover - import guard for CI without the wheel
    _Interpreter = None


PALM_INPUT_SIZE = 192
LANDMARK_INPUT_SIZE = 224
NUM_LANDMARKS = 21

# Landmark indices of the five fingertips (thumb, index, middle, ring, pinky).
FINGERTIP_IDS: tuple[int, ...] = (4, 8, 12, 16, 20)

# Bone connections for drawing the hand skeleton.
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


@dataclass
class Hand:
    """A detected hand.

    ``landmarks`` are 21 (x, y) points normalized to the source frame (0..1).
    ``score`` is the landmark model's hand-presence confidence and
    ``handedness`` is >0.5 for a right hand.
    """

    score: float
    handedness: float
    landmarks: np.ndarray  # (21, 2), normalized to the source frame

    def fingertips(self) -> list[tuple[float, float]]:
        return [(float(self.landmarks[i, 0]), float(self.landmarks[i, 1])) for i in FINGERTIP_IDS]


@dataclass
class _Region:
    """A palm/landmark ROI expressed in the padded square-image pixel space."""

    score: float = 0.0
    box: np.ndarray | None = None  # [x, y, w, h] normalized in the square image
    kps: np.ndarray | None = None  # (7, 2) normalized keypoints
    rect_center: tuple[float, float] = (0.0, 0.0)  # pixels
    rect_size: float = 0.0  # pixels (square)
    rotation: float = 0.0  # radians
    rect_points: list[list[float]] = field(default_factory=list)  # 4 corners, pixels


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _normalize_radians(angle: float) -> float:
    return angle - 2 * math.pi * math.floor((angle + math.pi) / (2 * math.pi))


def _calculate_scale(min_scale: float, max_scale: float, stride_index: int, num_strides: int) -> float:
    if num_strides == 1:
        return (min_scale + max_scale) / 2.0
    return min_scale + (max_scale - min_scale) * stride_index / (num_strides - 1)


def generate_anchors() -> np.ndarray:
    """Generate the 2016 BlazePalm SSD anchors for a 192x192 input.

    Matches MediaPipe's ssd_anchors_calculator options for palm_detection_full.
    """
    min_scale = 0.1484375
    max_scale = 0.75
    strides = [8, 16, 16, 16]
    input_size = PALM_INPUT_SIZE
    offset = 0.5
    anchors: list[list[float]] = []
    n_strides = len(strides)
    layer_id = 0
    while layer_id < n_strides:
        last = layer_id
        repeats = 0
        while last < n_strides and strides[last] == strides[layer_id]:
            # One anchor per aspect ratio (=[1.0]) plus one interpolated anchor.
            repeats += 2
            last += 1
        stride = strides[layer_id]
        feature_map = math.ceil(input_size / stride)
        for y in range(feature_map):
            for x in range(feature_map):
                for _ in range(repeats):
                    x_center = (x + offset) / feature_map
                    y_center = (y + offset) / feature_map
                    anchors.append([x_center, y_center, 1.0, 1.0])
        layer_id = last
    return np.array(anchors, dtype=np.float32)


def _decode_palms(
    scores: np.ndarray,
    boxes: np.ndarray,
    anchors: np.ndarray,
    score_thresh: float,
) -> list[_Region]:
    """Decode raw palm-detection tensors into normalized boxes + keypoints."""
    scores = _sigmoid(scores.reshape(-1))
    mask = scores > score_thresh
    if not np.any(mask):
        return []

    det_scores = scores[mask]
    det_boxes = boxes[mask]
    det_anchors = anchors[mask]

    # box/kp regression is relative to the anchor center, in input pixels.
    scale = float(PALM_INPUT_SIZE)
    decoded = det_boxes * np.tile(det_anchors[:, 2:4], 9) / scale + np.tile(det_anchors[:, 0:2], 9)
    decoded[:, 2:4] = decoded[:, 2:4] - det_anchors[:, 0:2]  # width, height
    decoded[:, 0:2] = decoded[:, 0:2] - decoded[:, 3:4] * 0.5  # center -> top-left

    regions: list[_Region] = []
    for i in range(decoded.shape[0]):
        box = decoded[i, 0:4]
        if box[2] < 0 or box[3] < 0:
            continue
        kps = decoded[i, 4:18].reshape(7, 2)
        regions.append(_Region(score=float(det_scores[i]), box=box.copy(), kps=kps.copy()))
    return regions


def _nms(regions: list[_Region], iou_thresh: float) -> list[_Region]:
    if not regions:
        return []
    boxes = np.array([r.box for r in regions], dtype=np.float32)
    scores = np.array([r.score for r in regions], dtype=np.float32)
    x1, y1 = boxes[:, 0], boxes[:, 1]
    x2, y2 = boxes[:, 0] + boxes[:, 2], boxes[:, 1] + boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        union = areas[i] + areas[order[1:]] - inter
        iou = np.where(union > 0, inter / union, 0.0)
        order = order[1:][iou <= iou_thresh]
    return [regions[i] for i in keep]


def _rotated_rect_points(cx: float, cy: float, size: float, rotation: float) -> list[list[float]]:
    b = math.cos(rotation) * 0.5
    a = math.sin(rotation) * 0.5
    p0x = cx - a * size - b * size
    p0y = cy + b * size - a * size
    p1x = cx + a * size - b * size
    p1y = cy - b * size - a * size
    p2x = 2 * cx - p0x
    p2y = 2 * cy - p0y
    p3x = 2 * cx - p1x
    p3y = 2 * cy - p1y
    return [[p0x, p0y], [p1x, p1y], [p2x, p2y], [p3x, p3y]]


def _palm_to_rect(region: _Region, image_size: int) -> None:
    """Build a wrist-aligned, expanded square ROI from a palm detection."""
    box = region.box
    kps = region.kps
    width = box[2]
    height = box[3]
    cx = box[0] + width / 2.0
    cy = box[1] + height / 2.0

    # Rotate so the wrist(0) -> middle-finger(2) axis aligns with the Y axis.
    x0, y0 = kps[0]
    x1, y1 = kps[2]
    rotation = _normalize_radians(math.pi * 0.5 - math.atan2(-(y1 - y0), x1 - x0))

    # Expand around the palm to cover the whole hand (MediaPipe uses 2.6; 2.9
    # keeps fingertips inside on splayed hands).
    scale = 2.9
    shift_y = -0.5
    long_side = max(width * image_size, height * image_size)
    size = long_side * scale
    x_shift = -image_size * height * shift_y * math.sin(rotation)
    y_shift = image_size * height * shift_y * math.cos(rotation)
    center_x = cx * image_size + x_shift
    center_y = cy * image_size + y_shift

    region.rect_center = (center_x, center_y)
    region.rect_size = size
    region.rotation = rotation
    region.rect_points = _rotated_rect_points(center_x, center_y, size, rotation)


def _landmarks_to_rect(landmarks_sq: np.ndarray) -> _Region:
    """Compute the next-frame ROI from the current landmarks (tracking)."""
    wrist = landmarks_sq[0]
    ref = 0.25 * (landmarks_sq[5] + landmarks_sq[13]) + 0.5 * landmarks_sq[9]
    rotation = _normalize_radians(0.5 * math.pi - math.atan2(wrist[1] - ref[1], ref[0] - wrist[0]))

    ids = [0, 1, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18]
    pts = landmarks_sq[ids]
    center_axis = 0.5 * (pts.min(axis=0) + pts.max(axis=0))
    centered = pts - center_axis
    c, s = math.cos(rotation), math.sin(rotation)
    rot = np.array(((c, -s), (s, c)), dtype=np.float32)
    projected = centered.dot(rot)
    min_p = projected.min(axis=0)
    max_p = projected.max(axis=0)
    proj_center = 0.5 * (min_p + max_p)
    center = rot.dot(proj_center) + center_axis
    width, height = (max_p - min_p)
    size = 2.0 * max(float(width), float(height))
    cx = float(center[0]) + 0.1 * float(height) * s
    cy = float(center[1]) - 0.1 * float(height) * c

    region = _Region(score=1.0, rotation=rotation, rect_center=(cx, cy), rect_size=size)
    region.rect_points = _rotated_rect_points(cx, cy, size, rotation)
    return region


class HandLandmarker:
    """Detect and track hands, returning 21 landmarks per hand."""

    def __init__(
        self,
        palm_model: str | Path,
        landmark_model: str | Path,
        *,
        palm_score_thresh: float = 0.5,
        landmark_score_thresh: float = 0.5,
        nms_thresh: float = 0.3,
        max_hands: int = 2,
        detect_period: int = 8,
        num_threads: int = 4,
    ) -> None:
        if _Interpreter is None:
            raise RuntimeError("ai-edge-litert is not installed; cannot run hand landmark tracking")

        self.palm_score_thresh = palm_score_thresh
        self.landmark_score_thresh = landmark_score_thresh
        self.nms_thresh = nms_thresh
        self.max_hands = max(1, int(max_hands))
        self.detect_period = max(1, int(detect_period))
        threads = max(1, int(num_threads))

        self._palm = _Interpreter(model_path=str(palm_model), num_threads=threads)
        self._palm.allocate_tensors()
        self._lm = _Interpreter(model_path=str(landmark_model), num_threads=threads)
        self._lm.allocate_tensors()

        self._palm_in = self._palm.get_input_details()[0]["index"]
        self._palm_out = self._resolve_palm_outputs()
        self._lm_in = self._lm.get_input_details()[0]["index"]
        self._lm_out = self._resolve_landmark_outputs()

        self._anchors = generate_anchors()
        self._tracked: list[_Region] = []
        self._frame = 0

    def _resolve_palm_outputs(self) -> tuple[int, int]:
        boxes_idx = scores_idx = None
        for detail in self._palm.get_output_details():
            if detail["shape"][-1] == 18:
                boxes_idx = detail["index"]
            elif detail["shape"][-1] == 1:
                scores_idx = detail["index"]
        if boxes_idx is None or scores_idx is None:
            raise RuntimeError("Unexpected palm-detection model outputs")
        return boxes_idx, scores_idx

    def _resolve_landmark_outputs(self) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for detail in self._lm.get_output_details():
            name = str(detail["name"])
            shape = list(detail["shape"])
            if shape[-1] == 63 and "landmarks" not in mapping and name.endswith("Identity"):
                mapping["landmarks"] = detail["index"]
            elif shape[-1] == 63 and name.endswith("Identity_3"):
                mapping["world"] = detail["index"]
            elif shape[-1] == 1 and name.endswith("Identity_1"):
                mapping["score"] = detail["index"]
            elif shape[-1] == 1 and name.endswith("Identity_2"):
                mapping["handedness"] = detail["index"]
        # Fall back to positional resolution if names differ across exports.
        if "landmarks" not in mapping or "score" not in mapping:
            details = sorted(self._lm.get_output_details(), key=lambda d: d["index"])
            sixty_three = [d for d in details if list(d["shape"])[-1] == 63]
            ones = [d for d in details if list(d["shape"])[-1] == 1]
            if sixty_three:
                mapping.setdefault("landmarks", sixty_three[0]["index"])
            if len(sixty_three) > 1:
                mapping.setdefault("world", sixty_three[1]["index"])
            if ones:
                mapping.setdefault("score", ones[0]["index"])
            if len(ones) > 1:
                mapping.setdefault("handedness", ones[1]["index"])
        return mapping

    def _detect_palms(self, square_rgb: np.ndarray, image_size: int) -> list[_Region]:
        resized = cv2.resize(square_rgb, (PALM_INPUT_SIZE, PALM_INPUT_SIZE), interpolation=cv2.INTER_AREA)
        tensor = (resized.astype(np.float32) / 255.0)[np.newaxis, ...]
        self._palm.set_tensor(self._palm_in, tensor)
        self._palm.invoke()
        boxes = self._palm.get_tensor(self._palm_out[0])[0]
        scores = self._palm.get_tensor(self._palm_out[1])[0]

        regions = _decode_palms(scores, boxes, self._anchors, self.palm_score_thresh)
        regions = _nms(regions, self.nms_thresh)
        regions.sort(key=lambda r: r.score, reverse=True)
        regions = regions[: self.max_hands]
        for region in regions:
            _palm_to_rect(region, image_size)
        return regions

    def _run_landmark(
        self,
        square_bgr: np.ndarray,
        region: _Region,
        pad_x: int,
        pad_y: int,
        src_w: int,
        src_h: int,
    ) -> tuple[Hand, _Region] | None:
        size = LANDMARK_INPUT_SIZE
        # rect_points[0] is the bottom-left corner; warp the other three.
        src = np.array(region.rect_points[1:], dtype=np.float32)
        dst = np.array([(0, 0), (size, 0), (size, size)], dtype=np.float32)
        mat = cv2.getAffineTransform(src, dst)
        crop = cv2.warpAffine(square_bgr, mat, (size, size))
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensor = (crop_rgb.astype(np.float32) / 255.0)[np.newaxis, ...]

        self._lm.set_tensor(self._lm_in, tensor)
        self._lm.invoke()
        score = float(_sigmoid(self._lm.get_tensor(self._lm_out["score"]).reshape(-1))[0])
        if score < self.landmark_score_thresh:
            return None
        handedness = float(_sigmoid(self._lm.get_tensor(self._lm_out["handedness"]).reshape(-1))[0])
        raw = self._lm.get_tensor(self._lm_out["landmarks"]).reshape(NUM_LANDMARKS, 3)

        # ROI-normalized (0..1) -> square-image pixels via the inverse warp.
        norm_xy = (raw[:, :2] / size).astype(np.float32)
        inv = cv2.invertAffineTransform(mat)
        square_xy = cv2.transform(norm_xy.reshape(-1, 1, 2) * size, inv).reshape(-1, 2)

        # square pixels -> source pixels -> normalized to the source frame.
        source_xy = square_xy - np.array([pad_x, pad_y], dtype=np.float32)
        norm_landmarks = source_xy / np.array([src_w, src_h], dtype=np.float32)

        hand = Hand(score=score, handedness=handedness, landmarks=norm_landmarks)
        next_region = _landmarks_to_rect(square_xy)
        return hand, next_region

    def process(self, frame_bgr: np.ndarray) -> list[Hand]:
        height, width = frame_bgr.shape[:2]
        if height == 0 or width == 0:
            return []

        image_size = max(width, height)
        pad_x = (image_size - width) // 2
        pad_y = (image_size - height) // 2
        square_bgr = cv2.copyMakeBorder(
            frame_bgr, pad_y, image_size - height - pad_y, pad_x, image_size - width - pad_x,
            cv2.BORDER_CONSTANT, value=(0, 0, 0),
        )

        force_detect = self._frame % self.detect_period == 0
        if self._tracked and not force_detect:
            regions = self._tracked
        else:
            square_rgb = cv2.cvtColor(square_bgr, cv2.COLOR_BGR2RGB)
            regions = self._detect_palms(square_rgb, image_size)

        hands: list[Hand] = []
        next_tracked: list[_Region] = []
        for region in regions:
            if not region.rect_points:
                continue
            result = self._run_landmark(square_bgr, region, pad_x, pad_y, width, height)
            if result is None:
                continue
            hand, next_region = result
            hands.append(hand)
            next_tracked.append(next_region)

        self._tracked = next_tracked[: self.max_hands]
        self._frame += 1
        return hands

    def reset(self) -> None:
        self._tracked = []
        self._frame = 0
