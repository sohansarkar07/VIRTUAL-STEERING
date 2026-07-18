"""
Virtual Steering — HUD Renderer Module
Draws the premium racing overlay on OpenCV frames.
"""

import math
import cv2
import numpy as np
from config import *


class HUDRenderer:
    """
    Renders the complete heads-up display:
      - Steering wheel visual (rotates with input)
      - RPM gauge (arc)
      - Speed gauge (arc)
      - Status bars (throttle / brake)
      - Telemetry text panel
      - Gesture + direction indicators
    """

    def __init__(self, frame_w: int, frame_h: int):
        self.fw = frame_w
        self.fh = frame_h

        # Pre-compute fixed positions
        self.wheel_cx = int(frame_w * WHEEL_CENTER_X_RATIO)
        self.wheel_cy = int(frame_h * WHEEL_CENTER_Y_RATIO)

        # Gauge positions
        self.rpm_center   = (int(frame_w * 0.18), int(frame_h * 0.28))
        self.speed_center = (int(frame_w * 0.82), int(frame_h * 0.28))
        self.gauge_r      = int(frame_h * 0.14)

        # Fonts
        self.font       = FONT
        self.f_large    = FONT_SCALE_LARGE
        self.f_med      = FONT_SCALE_MEDIUM
        self.f_small    = FONT_SCALE_SMALL
        self.f_thick    = FONT_THICKNESS

    # ──────────────────────────────────────────
    # Main draw call
    # ──────────────────────────────────────────

    def draw(
        self,
        frame:          np.ndarray,
        steering_angle: float,
        gesture:        str,
        hands:          list,
        fps:            float,
        simulated_speed: float,
        simulated_rpm:   float,
        throttle:       float,
        brake:          float,
        active_keys:    set,
    ):
        overlay = frame.copy()

        self._draw_dark_panels(overlay, steering_angle, throttle, brake)
        self._draw_rpm_gauge(overlay, simulated_rpm)
        self._draw_speed_gauge(overlay, simulated_speed)
        self._draw_steering_wheel(overlay, steering_angle)
        self._draw_gesture_indicator(overlay, gesture, hands)
        self._draw_active_keys(overlay, active_keys)
        self._draw_telemetry(overlay, steering_angle, fps, simulated_speed, simulated_rpm)
        self._draw_throttle_brake(overlay, throttle, brake)
        self._draw_header(overlay)

        # Blend overlay with original frame
        cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)

    # ──────────────────────────────────────────
    # Component renderers
    # ──────────────────────────────────────────

    def _draw_dark_panels(self, frame, steering_angle, throttle, brake):
        """Semi-transparent dark background panels."""
        panels = [
            # (x1, y1, x2, y2)
            (0,           0,           self.fw,              55),    # top bar
            (0,           self.fh-180, self.fw,              self.fh),  # bottom bar
            (0,           55,          int(self.fw*0.32),    self.fh-180),  # left gauge
            (int(self.fw*0.68), 55,    self.fw,              self.fh-180),  # right gauge
        ]
        panel_overlay = frame.copy()
        for (x1, y1, x2, y2) in panels:
            cv2.rectangle(panel_overlay, (x1, y1), (x2, y2), (10, 8, 18), -1)
        cv2.addWeighted(panel_overlay, HUD_PANEL_ALPHA, frame, 1 - HUD_PANEL_ALPHA, 0, frame)

    def _draw_header(self, frame):
        """Top banner with logo and status."""
        # Logo text
        cv2.putText(frame, "VIRTUAL STEERING", (18, 36),
                    self.font, 0.90, COLOR_ACCENT, 2, cv2.LINE_AA)
        # Separator line
        cv2.line(frame, (0, 54), (self.fw, 54), COLOR_ACCENT, 1)
        # Status dot
        cv2.circle(frame, (self.fw - 24, 28), 7, COLOR_GREEN, -1)
        cv2.putText(frame, "ACTIVE", (self.fw - 110, 34),
                    self.font, 0.48, COLOR_GREEN, 1, cv2.LINE_AA)

    def _draw_rpm_gauge(self, frame, rpm: float):
        """Arc RPM gauge — left side."""
        cx, cy = self.rpm_center
        r = self.gauge_r
        self._draw_arc_gauge(
            frame, cx, cy, r,
            value=rpm, max_val=GAUGE_RPM_MAX,
            label="RPM",
            unit=f"{int(rpm):,}",
            start_ang=150, end_ang=390,
            color_low=COLOR_GREEN,
            color_high=COLOR_RED,
        )

    def _draw_speed_gauge(self, frame, speed: float):
        """Arc speed gauge — right side."""
        cx, cy = self.speed_center
        r = self.gauge_r
        self._draw_arc_gauge(
            frame, cx, cy, r,
            value=speed, max_val=GAUGE_SPEED_MAX,
            label="SPEED",
            unit=f"{int(speed)} km/h",
            start_ang=150, end_ang=390,
            color_low=COLOR_ACCENT,
            color_high=COLOR_YELLOW,
        )

    def _draw_arc_gauge(
        self, frame, cx, cy, r,
        value, max_val, label, unit,
        start_ang, end_ang,
        color_low, color_high,
    ):
        """Generic arc gauge renderer."""
        # Background arc
        cv2.ellipse(frame, (cx, cy), (r, r), 0,
                    start_ang, end_ang, COLOR_DIM, 6, cv2.LINE_AA)

        # Filled arc up to current value
        ratio    = min(max(value / max_val, 0.0), 1.0)
        fill_end = start_ang + (end_ang - start_ang) * ratio

        # Interpolate color
        t = ratio
        color = (
            int(color_low[0] * (1-t) + color_high[0] * t),
            int(color_low[1] * (1-t) + color_high[1] * t),
            int(color_low[2] * (1-t) + color_high[2] * t),
        )
        if ratio > 0.01:
            cv2.ellipse(frame, (cx, cy), (r, r), 0,
                        start_ang, fill_end, color, 7, cv2.LINE_AA)

        # Needle dot at tip
        ang_rad = math.radians(fill_end)
        nx = int(cx + r * math.cos(ang_rad))
        ny = int(cy + r * math.sin(ang_rad))
        cv2.circle(frame, (nx, ny), 6, color, -1, cv2.LINE_AA)

        # Label & value text
        cv2.putText(frame, label, (cx - 30, cy + r + 22),
                    self.font, self.f_small, COLOR_DIM, 1, cv2.LINE_AA)
        cv2.putText(frame, unit, (cx - 45, cy + r + 46),
                    self.font, self.f_small + 0.1, COLOR_WHITE, 1, cv2.LINE_AA)

    def _draw_steering_wheel(self, frame, angle: float):
        """Animated steering wheel that rotates with angle."""
        cx, cy = self.wheel_cx, self.wheel_cy
        R  = WHEEL_RADIUS
        Hr = HUB_RADIUS
        angle_rad = math.radians(angle)

        # Outer rim
        cv2.circle(frame, (cx, cy), R, COLOR_WHEEL_RIM, 4, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), R - 8, (25, 22, 40), 3, cv2.LINE_AA)

        # 3 spokes (rotated by steering angle)
        for i in range(3):
            base_ang = angle_rad + math.radians(i * 120)
            x1 = int(cx + Hr * 1.5 * math.cos(base_ang))
            y1 = int(cy + Hr * 1.5 * math.sin(base_ang))
            x2 = int(cx + (R - 10) * math.cos(base_ang))
            y2 = int(cy + (R - 10) * math.sin(base_ang))
            cv2.line(frame, (x1, y1), (x2, y2), COLOR_WHEEL_RIM, 5, cv2.LINE_AA)

        # Center hub
        cv2.circle(frame, (cx, cy), Hr, COLOR_WHEEL_HUB, -1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), Hr, COLOR_WHEEL_RIM, 2, cv2.LINE_AA)

        # Top marker (12 o'clock reference)
        top_x = int(cx + R * math.cos(angle_rad - math.pi/2))
        top_y = int(cy + R * math.sin(angle_rad - math.pi/2))
        cv2.circle(frame, (top_x, top_y), 5, COLOR_YELLOW, -1, cv2.LINE_AA)

        # Angle label
        ang_text = f"{angle:+.1f}°"
        tw, _ = cv2.getTextSize(ang_text, self.font, self.f_small, 1)[0], 0
        cv2.putText(frame, ang_text,
                    (cx - 30, cy + R + 28),
                    self.font, self.f_small + 0.05, COLOR_ACCENT, 1, cv2.LINE_AA)
        cv2.putText(frame, "STEERING",
                    (cx - 36, cy + R + 46),
                    self.font, self.f_small - 0.05, COLOR_DIM, 1, cv2.LINE_AA)

    def _draw_gesture_indicator(self, frame, gesture: str, hands: list):
        """Shows hand gesture status icons and wrist line."""
        # Gesture box
        gesture_colors = {
            "fist":    (COLOR_GREEN,  "FIST  ✦ GAS"),
            "open":    (COLOR_RED,    "OPEN  ✦ BRAKE"),
            "neutral": (COLOR_DIM,    "NEUTRAL"),
        }
        color, text = gesture_colors.get(gesture, (COLOR_DIM, gesture.upper()))

        x0, y0 = int(self.fw * 0.38), self.fh - 168
        cv2.rectangle(frame, (x0, y0), (x0 + 220, y0 + 36), (20, 18, 32), -1)
        cv2.rectangle(frame, (x0, y0), (x0 + 220, y0 + 36), color, 1)
        cv2.putText(frame, text, (x0 + 10, y0 + 24),
                    self.font, self.f_small + 0.05, color, 1, cv2.LINE_AA)

        # Wrist-to-wrist line when 2 hands detected
        if len(hands) == 2:
            p1 = (hands[0]["x"], hands[0]["y"])
            p2 = (hands[1]["x"], hands[1]["y"])
            cv2.line(frame, p1, p2, COLOR_ACCENT, 2, cv2.LINE_AA)
            cv2.circle(frame, p1, 8, COLOR_ACCENT, -1)
            cv2.circle(frame, p2, 8, COLOR_ACCENT, -1)

    def _draw_active_keys(self, frame, active_keys: set):
        """Key press indicator row."""
        key_defs = [
            (KEY_LEFT,  "◄ LEFT",  "left"),
            (KEY_RIGHT, "RIGHT ►", "right"),
            (KEY_GAS,   "▲ GAS",   "up"),
            (KEY_BRAKE, "▼ BRAKE", "down"),
        ]
        bx, by = int(self.fw * 0.28), self.fh - 110
        for i, (key, label, match) in enumerate(key_defs):
            active = match in active_keys
            col    = COLOR_ACCENT if active else COLOR_DIM
            bg_col = (0, 50, 60) if active else (12, 10, 20)
            bw, bh = 130, 32
            x = bx + i * (bw + 8)
            cv2.rectangle(frame, (x, by), (x + bw, by + bh), bg_col, -1)
            cv2.rectangle(frame, (x, by), (x + bw, by + bh), col, 1)
            cv2.putText(frame, label, (x + 10, by + 21),
                        self.font, self.f_small, col, 1, cv2.LINE_AA)

    def _draw_telemetry(self, frame, steering_angle, fps, speed, rpm):
        """Left-side telemetry text panel."""
        x, y = 14, self.fh - 170
        items = [
            ("ANGLE",  f"{steering_angle:+6.1f}°",  COLOR_ACCENT),
            ("SPEED",  f"{speed:6.1f} km/h",         COLOR_WHITE),
            ("RPM",    f"{int(rpm):6,}",              COLOR_YELLOW),
            ("FPS",    f"{fps:6.1f}",                 COLOR_GREEN if fps > 45 else COLOR_RED),
        ]
        for label, val, col in items:
            cv2.putText(frame, label, (x, y),
                        self.font, self.f_small, COLOR_DIM, 1, cv2.LINE_AA)
            cv2.putText(frame, val, (x + 70, y),
                        self.font, self.f_small, col, 1, cv2.LINE_AA)
            y += 26

    def _draw_throttle_brake(self, frame, throttle: float, brake: float):
        """Vertical bar indicators for throttle and brake — right side."""
        bar_h  = 130
        bar_w  = 18
        x_thr  = self.fw - 50
        x_brk  = self.fw - 28
        y_top  = self.fh - 175

        for (x, value, color, label) in [
            (x_thr, throttle, COLOR_GREEN, "T"),
            (x_brk, brake,    COLOR_RED,   "B"),
        ]:
            # Background
            cv2.rectangle(frame, (x, y_top), (x + bar_w, y_top + bar_h),
                          (20, 18, 30), -1)
            cv2.rectangle(frame, (x, y_top), (x + bar_w, y_top + bar_h),
                          COLOR_DIM, 1)
            # Fill
            fill_h = int(bar_h * value)
            if fill_h > 0:
                cv2.rectangle(frame,
                              (x, y_top + bar_h - fill_h),
                              (x + bar_w, y_top + bar_h),
                              color, -1)
            cv2.putText(frame, label, (x + 5, y_top - 6),
                        self.font, self.f_small, color, 1, cv2.LINE_AA)

    def draw_no_hands(self, frame):
        """Overlay shown when no hands detected."""
        msg = "SHOW BOTH HANDS TO CAMERA"
        tw  = cv2.getTextSize(msg, self.font, 0.80, 2)[0][0]
        cx  = (self.fw - tw) // 2
        cy  = self.fh // 2 - 20
        cv2.putText(frame, msg, (cx, cy),
                    self.font, 0.80, COLOR_YELLOW, 2, cv2.LINE_AA)

    def draw_quit_hint(self, frame):
        cv2.putText(frame, "Press  Q  to quit",
                    (self.fw - 200, self.fh - 12),
                    self.font, self.f_small, COLOR_DIM, 1, cv2.LINE_AA)
