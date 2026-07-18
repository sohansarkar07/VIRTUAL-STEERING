"""
Virtual Steering — Physics Simulation Engine
Simulates vehicle telemetry (speed, RPM, throttle, brake) 
based on gesture inputs. Runs at ~60fps.
"""

import time
from config import GAUGE_RPM_MAX, GAUGE_SPEED_MAX


# Gear ratios: gear index → ratio multiplier
_GEAR_RATIOS = [0, 3.5, 2.1, 1.5, 1.1, 0.85, 0.70]   # 0 = neutral
_REDLINE_RPM = 7200


class PhysicsEngine:
    """
    Lightweight vehicle physics for realistic telemetry display.
    Not a full rigid-body sim — tuned for visual feedback.
    """

    def __init__(self):
        self.speed       = 0.0     # km/h
        self.rpm         = 800.0   # engine idle
        self.throttle    = 0.0     # 0–1
        self.brake       = 0.0     # 0–1
        self.gear        = 1
        self._last_tick  = time.time()

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def tick(self, gesture: str) -> dict:
        """
        Advance simulation by one frame.
        Returns dict of current telemetry values.
        """
        now  = time.time()
        dt   = min(now - self._last_tick, 0.05)   # cap delta time
        self._last_tick = now

        # Resolve inputs from gesture
        target_throttle = 1.0 if gesture == "fist"   else 0.0
        target_brake    = 1.0 if gesture == "open"   else 0.0

        # Smooth pedal response
        self.throttle = _lerp(self.throttle, target_throttle, dt * 6.0)
        self.brake    = _lerp(self.brake,    target_brake,    dt * 8.0)

        # Speed dynamics
        accel_force  = self.throttle * 28.0    # km/h per second
        brake_force  = self.brake    * 60.0    # strong braking
        drag         = self.speed    * 0.018   # aerodynamic drag

        self.speed = max(
            0.0,
            min(
                GAUGE_SPEED_MAX,
                self.speed + (accel_force - brake_force - drag) * dt
            )
        )

        # Auto gear shift
        self._auto_shift()

        # RPM derived from speed + gear ratio
        ratio      = _GEAR_RATIOS[self.gear]
        target_rpm = self.speed * ratio * 28 + 800
        target_rpm = min(target_rpm, GAUGE_RPM_MAX)
        self.rpm   = _lerp(self.rpm, target_rpm, dt * 4.0)

        # Rev-limiter bounce
        if self.rpm >= _REDLINE_RPM and self.throttle > 0.8:
            self.rpm = _REDLINE_RPM * 0.92

        return {
            "speed":    self.speed,
            "rpm":      self.rpm,
            "throttle": self.throttle,
            "brake":    self.brake,
            "gear":     self.gear,
        }

    def reset(self):
        self.speed    = 0.0
        self.rpm      = 800.0
        self.throttle = 0.0
        self.brake    = 0.0
        self.gear     = 1

    # ──────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────

    def _auto_shift(self):
        """Simple automatic gearbox based on speed thresholds."""
        thresholds = [0, 0, 40, 80, 130, 190, 260]   # shift-up speeds
        if self.gear < 6 and self.speed > thresholds[self.gear + 1]:
            self.gear += 1
        elif self.gear > 1 and self.speed < thresholds[self.gear] * 0.75:
            self.gear -= 1


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * min(max(t, 0.0), 1.0)
