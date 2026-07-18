# ─────────────────────────────────────────────
#  Virtual Steering — Configuration
# ─────────────────────────────────────────────

# ── Camera ──────────────────────────────────
CAMERA_INDEX        = 0          # Webcam index (0 = default)
FRAME_WIDTH         = 1280       # Capture width
FRAME_HEIGHT        = 720        # Capture height
FLIP_HORIZONTAL     = True       # Mirror mode (selfie view)

# ── MediaPipe Hands ─────────────────────────
MAX_HANDS           = 2          # Track both hands
DETECTION_CONF      = 0.75       # Hand detection confidence threshold
TRACKING_CONF       = 0.65       # Hand tracking confidence threshold

# ── Steering ────────────────────────────────────
STEERING_DEADZONE   = 4          # Degrees — was 8, lowered for responsiveness
STEERING_THRESHOLD  = 11         # Degrees beyond deadzone to steer (was 22)
                                 # Total angle needed = DEADZONE + THRESHOLD = 15°
MAX_STEERING_ANGLE  = 90         # Maximum wrist tilt angle (degrees)
SMOOTHING_FACTOR    = 0.25       # EMA smoothing (was 0.35, faster now)

# ── Throttle / Brake ────────────────────────
FIST_THRESHOLD      = 0.055      # Finger curl sum below this = fist (gas)
OPEN_THRESHOLD      = 0.20       # Finger spread above this = open (brake)
ACTION_COOLDOWN_MS  = 80         # Min ms between repeated key presses

# ── Key Bindings ────────────────────────────
KEY_LEFT            = 'left'
KEY_RIGHT           = 'right'
KEY_GAS             = 'up'
KEY_BRAKE           = 'down'

# ── HUD Colors (BGR for OpenCV) ─────────────
COLOR_BG            = (15,  12,  20)    # Near-black purple-tinted background
COLOR_ACCENT        = (0,   200, 255)   # Neon cyan
COLOR_RED           = (50,  50,  220)   # Racing red
COLOR_GREEN         = (50,  220, 120)   # OK green
COLOR_YELLOW        = (0,   200, 220)   # Warning yellow
COLOR_WHITE         = (240, 240, 240)   # Off-white text
COLOR_DIM           = (90,  90,  110)   # Dimmed labels
COLOR_WHEEL_RIM     = (0,   160, 220)   # Wheel rim neon
COLOR_WHEEL_HUB     = (40,  40,  55)    # Wheel hub dark

# ── HUD Layout ──────────────────────────────
HUD_PANEL_ALPHA     = 0.72       # Transparency of HUD panels (0–1)
FONT_SCALE_LARGE    = 1.4
FONT_SCALE_MEDIUM   = 0.75
FONT_SCALE_SMALL    = 0.52
FONT_THICKNESS      = 2
FONT                = 0          # cv2.FONT_HERSHEY_SIMPLEX

# ── Steering Wheel Rendering ─────────────────
WHEEL_CENTER_X_RATIO = 0.50      # Fraction of frame width
WHEEL_CENTER_Y_RATIO = 0.78      # Fraction of frame height
WHEEL_RADIUS        = 105        # Outer rim radius (pixels)
HUB_RADIUS          = 18         # Center hub radius

# ── Gauge Rendering ──────────────────────────
GAUGE_RPM_MAX       = 8000
GAUGE_SPEED_MAX     = 300
