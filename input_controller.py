"""
Virtual Steering — Input Controller Module
Translates gesture+angle state into keyboard events via pynput.
"""

import time
from pynput.keyboard import Controller, Key
from config import (
    KEY_LEFT, KEY_RIGHT, KEY_GAS, KEY_BRAKE,
    STEERING_DEADZONE, STEERING_THRESHOLD,
    ACTION_COOLDOWN_MS,
)


_KEY_MAP = {
    "left":  Key.left,
    "right": Key.right,
    "up":    Key.up,
    "down":  Key.down,
}


class InputController:
    """
    Sends keyboard press/release events based on virtual steering state.
    Uses pynput for OS-level key injection (works with games).
    """

    def __init__(self):
        self._kb        = Controller()
        self._pressed   = set()                    # currently held keys
        self._last_time = {}                       # cooldown tracker per key

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def update(self, steering_angle: float, gesture: str):
        """
        Call every frame with:
          steering_angle : smoothed angle in degrees (+right, -left)
          gesture        : 'fist' | 'open' | 'neutral'
        """
        desired = self._compute_desired_keys(steering_angle, gesture)
        self._sync_keys(desired)

    def release_all(self):
        """Release all currently pressed keys (call on exit)."""
        for k in list(self._pressed):
            self._release(k)

    # ──────────────────────────────────────────
    # Private logic
    # ──────────────────────────────────────────

    def _compute_desired_keys(self, angle: float, gesture: str) -> set:
        desired = set()

        # ── Steering ──
        if angle < -(STEERING_DEADZONE + STEERING_THRESHOLD):
            desired.add(KEY_LEFT)
        elif angle > (STEERING_DEADZONE + STEERING_THRESHOLD):
            desired.add(KEY_RIGHT)

        # ── Throttle / Brake ──
        if gesture == "fist":
            desired.add(KEY_GAS)
        elif gesture == "open":
            desired.add(KEY_BRAKE)

        return desired

    def _sync_keys(self, desired: set):
        # Release keys no longer needed
        for k in list(self._pressed):
            if k not in desired:
                self._release(k)

        # Press newly required keys (with cooldown)
        for k in desired:
            if k not in self._pressed:
                self._press(k)

    def _press(self, key_str: str):
        key = _KEY_MAP.get(key_str)
        if key is None:
            return
        now = time.time() * 1000
        last = self._last_time.get(key_str, 0)
        if now - last < ACTION_COOLDOWN_MS:
            return
        self._kb.press(key)
        self._pressed.add(key_str)
        self._last_time[key_str] = now

    def _release(self, key_str: str):
        key = _KEY_MAP.get(key_str)
        if key is None:
            return
        self._kb.release(key)
        self._pressed.discard(key_str)
