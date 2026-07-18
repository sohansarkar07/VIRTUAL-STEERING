"""
Virtual Steering — Hand Tracker Module (mediapipe 0.10+ Tasks API)
Wraps mediapipe.tasks.python.vision.HandLandmarker for landmark detection
and gesture classification. Auto-downloads the model on first run.
"""
import os
os.environ.setdefault("GLOG_minloglevel",        "3")  # suppress TF/mediapipe logs
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL",   "3")
os.environ.setdefault("MEDIAPIPE_DISABLE_GPU",  "1")

import math
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
import numpy as np

from config import (
    MAX_HANDS, DETECTION_CONF, TRACKING_CONF,
)

# ── Model ────────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# Hand skeleton connections (landmark index pairs)
_HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),            # Thumb
    (0,5),(5,6),(6,7),(7,8),            # Index
    (5,9),(9,10),(10,11),(11,12),       # Middle
    (9,13),(13,14),(14,15),(15,16),     # Ring
    (13,17),(0,17),(17,18),(18,19),(19,20),  # Pinky
]

# Fist/open thresholds — lowered OPEN threshold so spread fingers trigger easily
# avg_curl range: ~0.3 (tight fist) → ~2.0 (fingers fully spread)
_FIST_CURL_MAX = 0.65   # below this = fist  (was 0.60)
_OPEN_CURL_MIN = 0.85   # above this = open  (was 1.55 / 1.10)


def _ensure_model() -> None:
    """Download the hand landmarker model if not present."""
    if os.path.exists(MODEL_PATH):
        return
    print("[INFO]  Downloading hand landmarker model (~3 MB) — one-time setup...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[INFO]  Model downloaded successfully.")
    except Exception as e:
        raise RuntimeError(
            f"[ERROR] Failed to download hand landmarker model: {e}\n"
            f"        Download manually from:\n  {MODEL_URL}\n"
            f"        Save as: {MODEL_PATH}"
        ) from e


class HandTracker:
    """
    Manages the mediapipe HandLandmarker (Tasks API, VIDEO mode).
    Provides:
      - frame-by-frame landmark detection (process)
      - OpenCV-drawn skeleton overlay (draw_landmarks)
      - wrist positions + gesture classification (get_wrists)
    """

    def __init__(self):
        _ensure_model()

        base_opts = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
        options   = mp_vision.HandLandmarkerOptions(
            base_options                = base_opts,
            running_mode               = mp_vision.RunningMode.VIDEO,
            num_hands                  = MAX_HANDS,
            min_hand_detection_confidence = DETECTION_CONF,
            min_hand_presence_confidence  = 0.5,
            min_tracking_confidence       = TRACKING_CONF,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
        self.results     = None

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def process(self, frame_rgb: np.ndarray, timestamp_ms: int):
        """
        Run hand detection on an RGB frame.
        timestamp_ms MUST be monotonically increasing (use time.time()*1000).
        Stores results internally and returns them.
        """
        mp_image     = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        self.results = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        return self.results

    def draw_landmarks(self, frame_bgr: np.ndarray):
        """Draw hand skeleton on a BGR frame using OpenCV (in-place)."""
        if not self.results or not self.results.hand_landmarks:
            return

        h, w = frame_bgr.shape[:2]
        for hand_lms in self.results.hand_landmarks:
            pts = [
                (int(lm.x * w), int(lm.y * h))
                for lm in hand_lms
            ]
            # Connections
            for a, b in _HAND_CONNECTIONS:
                cv2.line(frame_bgr, pts[a], pts[b],
                         (0, 180, 210), 2, cv2.LINE_AA)
            # Joints
            for pt in pts:
                cv2.circle(frame_bgr, pt, 4, (0, 230, 255), -1, cv2.LINE_AA)
            # Wrist highlight
            cv2.circle(frame_bgr, pts[0], 7, (0, 200, 255), 2, cv2.LINE_AA)

    def get_wrists(self, frame_shape: tuple) -> list[dict]:
        """
        Returns list of dicts for each detected hand:
          {label, x, y, gesture, landmarks}
        Coordinates are in pixels.
        """
        if not self.results or not self.results.hand_landmarks:
            return []

        h, w = frame_shape[:2]
        hands_data = []

        for i, hand_lms in enumerate(self.results.hand_landmarks):
            # Handedness label
            label = "Unknown"
            if self.results.handedness and i < len(self.results.handedness):
                label = self.results.handedness[i][0].category_name

            # Wrist = landmark index 0
            wrist = hand_lms[0]
            wx, wy = int(wrist.x * w), int(wrist.y * h)

            gesture = self._classify_gesture(hand_lms)

            hands_data.append({
                "label":     label,
                "x":         wx,
                "y":         wy,
                "gesture":   gesture,
                "landmarks": hand_lms,
            })

        return hands_data

    def close(self):
        """Release the HandLandmarker."""
        self._landmarker.close()

    # ──────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _classify_gesture(hand_lms) -> str:
        """
        Classify gesture from normalized landmark list.
        Computes average tip-to-MCP distance normalized by hand size.

          avg_curl < 0.60  → 'fist'   (accelerate)
          avg_curl > 1.55  → 'open'   (brake)
          otherwise        → 'neutral'
        """
        TIPS = [8, 12, 16, 20]
        MCPS = [5,  9, 13, 17]   # MCP joints (knuckles)

        hand_size = math.dist(
            (hand_lms[0].x, hand_lms[0].y),
            (hand_lms[9].x, hand_lms[9].y),
        )
        if hand_size < 1e-5:
            return "neutral"

        curl_sum = sum(
            math.dist((hand_lms[tip].x, hand_lms[tip].y),
                      (hand_lms[mcp].x, hand_lms[mcp].y))
            / hand_size
            for tip, mcp in zip(TIPS, MCPS)
        )
        avg_curl = curl_sum / 4.0

        if avg_curl < _FIST_CURL_MAX:
            return "fist"
        elif avg_curl > _OPEN_CURL_MIN:
            return "open"
        return "neutral"
