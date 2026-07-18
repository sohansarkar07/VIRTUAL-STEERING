"""
Virtual Steering — Main Application Entry Point
=====================================================
Controls a game using hand gestures detected by webcam.
"""
# Suppress noisy mediapipe / TensorFlow logs before ANY imports
import os
os.environ.setdefault("GLOG_minloglevel",       "3")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL",  "3")
os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")

import argparse
import math
import sys
import time
import cv2
import numpy as np

from config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT, FLIP_HORIZONTAL,
    SMOOTHING_FACTOR, STEERING_DEADZONE, MAX_STEERING_ANGLE,
    COLOR_ACCENT, COLOR_RED, COLOR_YELLOW, COLOR_DIM, COLOR_WHITE,
)
from hand_tracker     import HandTracker
from input_controller import InputController
from hud_renderer     import HUDRenderer
from physics_engine   import PhysicsEngine


# ──────────────────────────────────────────────────────────────
# Steering angle computation
# ──────────────────────────────────────────────────────────────

def compute_steering_angle(hands: list) -> float | None:
    """
    Compute steering angle from wrist positions of two hands.
    Positive = right tilt, Negative = left tilt.
    Returns None if fewer than 2 hands detected.
    """
    if len(hands) < 2:
        return None

    # Sort by x so left hand is always index 0
    sorted_hands = sorted(hands, key=lambda h: h["x"])
    lh, rh = sorted_hands[0], sorted_hands[1]

    dx = rh["x"] - lh["x"]
    dy = rh["y"] - lh["y"]

    if abs(dx) < 10:   # hands too close horizontally
        return 0.0

    angle = math.degrees(math.atan2(dy, dx))
    # atan2 gives angle of line from left→right hand
    # Negative dy = right hand lower = tilt right → positive steering
    return float(np.clip(angle, -MAX_STEERING_ANGLE, MAX_STEERING_ANGLE))


def dominant_gesture(hands: list) -> str:
    """
    Determine the dominant gesture across all detected hands.
    Rules (priority order):
      1. ANY hand open  → 'open'  (brake — safety first)
      2. ALL hands fist → 'fist'  (gas only when committed)
      3. Otherwise      → 'neutral'
    """
    if not hands:
        return "neutral"
    gestures = [h["gesture"] for h in hands]
    if "open" in gestures:              # even one open hand = brake
        return "open"
    if "fist" in gestures:              # any fist = gas
        return "fist"
    return "neutral"


# ──────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────

def run(camera_idx: int, send_keys: bool):
    # ── Camera setup ──
    cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 60)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # minimize latency

    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {camera_idx}")
        sys.exit(1)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO]  Camera {camera_idx} opened at {actual_w}×{actual_h}")

    # ── Module init ──
    tracker   = HandTracker()
    hud       = HUDRenderer(actual_w, actual_h)
    physics   = PhysicsEngine()
    controller = InputController() if send_keys else None

    # ── State ──
    smoothed_angle = 0.0
    fps            = 0.0
    frame_count    = 0
    fps_timer      = time.time()
    active_keys    = set()
    start_time_ms  = int(time.time() * 1000)   # base for monotonic timestamp

    # Window
    win_name = "Virtual Steering  |  Press Q to quit"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, actual_w, actual_h)

    print("[INFO]  Starting. Show both hands to camera.")
    print("[INFO]  Q = quit  |  R = reset physics")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARN]  Frame read failed — retrying...")
                time.sleep(0.01)
                continue

            if FLIP_HORIZONTAL:
                frame = cv2.flip(frame, 1)

            # ── Hand tracking ──
            rgb        = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ts_ms      = int(time.time() * 1000) - start_time_ms
            tracker.process(rgb, ts_ms)
            tracker.draw_landmarks(frame)
            hands = tracker.get_wrists(frame.shape)

            # ── Steering angle ──
            raw_angle = compute_steering_angle(hands)
            if raw_angle is not None:
                smoothed_angle = (
                    SMOOTHING_FACTOR * smoothed_angle
                    + (1 - SMOOTHING_FACTOR) * raw_angle
                )
            else:
                # Gradually return to center when hands lost
                smoothed_angle *= 0.88

            gesture = dominant_gesture(hands)

            # ── Physics tick ──
            telem = physics.tick(gesture)

            # ── Key output ──
            if controller:
                controller.update(smoothed_angle, gesture)
                active_keys = set(controller._pressed)
            else:
                active_keys = set()

            # ── FPS calc ──
            frame_count += 1
            if frame_count % 20 == 0:
                now = time.time()
                fps = 20.0 / (now - fps_timer + 1e-9)
                fps_timer = now

            # ── HUD render ──
            if len(hands) < 1:
                hud.draw_no_hands(frame)
            else:
                hud.draw(
                    frame,
                    steering_angle  = smoothed_angle,
                    gesture         = gesture,
                    hands           = hands,
                    fps             = fps,
                    simulated_speed = telem["speed"],
                    simulated_rpm   = telem["rpm"],
                    throttle        = telem["throttle"],
                    brake           = telem["brake"],
                    active_keys     = active_keys,
                )

            hud.draw_quit_hint(frame)
            cv2.imshow(win_name, frame)

            # ── Key handling ──
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('r'):
                physics.reset()
                smoothed_angle = 0.0
                print("[INFO]  Physics reset.")

    finally:
        print("[INFO]  Shutting down...")
        if controller:
            controller.release_all()
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO]  Done.")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Virtual Steering — Control games with hand gestures"
    )
    parser.add_argument("--camera",   type=int,  default=CAMERA_INDEX,
                        help="Camera device index (default: 0)")
    parser.add_argument("--no-keys",  action="store_true",
                        help="Disable keyboard output (visualization only)")
    parser.add_argument("--demo",     action="store_true",
                        help="Demo mode: no keyboard output")
    args = parser.parse_args()

    send_keys = not (args.no_keys or args.demo)

    if send_keys:
        print("[INFO]  Keyboard control ENABLED — make sure a game is focused!")
    else:
        print("[INFO]  Keyboard control DISABLED — visualization mode only.")

    run(camera_idx=args.camera, send_keys=send_keys)
