import time
import random
import board
import busio
from adafruit_pca9685 import PCA9685

# =====================================================
# CONFIGURATION
# =====================================================

# Initialize I2C + PCA9685
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50  # 50 Hz for servos

# Servo channels
LEFT_X = 0
LEFT_Y = 1
LEFT_BLINK = 2
RIGHT_X = 3
RIGHT_Y = 4
RIGHT_BLINK = 5

# Travel limits
X_LIMITS = (70, 110)
Y_LIMITS = (70, 110)
BLINK_LIMITS = (0, 40)  # (open, closed)

# Servo direction multipliers
DIR_LEFT_X = 1
DIR_LEFT_Y = 1
DIR_LEFT_BLINK = 1

DIR_RIGHT_X = 1
DIR_RIGHT_Y = -1
DIR_RIGHT_BLINK = -1

# Blink open trims
BLINK_OPEN_LEFT = -12
BLINK_OPEN_RIGHT = 0

# Blink timing offsets
BLINK_SIDE_DELAY = 0.03

# Movement speed settings
MOVE_STEP = 1
MOVE_DELAY = 0.01
BLINK_INTERVAL = (4, 12)     # seconds between blinks
BLINK_SPEED = 0.003          # time per blink step
BLINK_HOLD = 0.10            # closed duration

# Pulse width settings
MIN_PULSE_MS = 0.5
MAX_PULSE_MS = 2.5
PERIOD_MS = 20.0


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def set_servo_angle(channel, direction, angle):
    """Set a servo angle (0–180°) with optional direction inversion."""
    if direction == -1:
        angle = 180 - angle

    pulse_range = MAX_PULSE_MS - MIN_PULSE_MS
    pulse_width = MIN_PULSE_MS + (pulse_range * angle / 180.0)
    duty_cycle = int((pulse_width / PERIOD_MS) * 65535)
    pca.channels[channel].duty_cycle = duty_cycle


def move_servos_together(angles_dict, current_angles):
    """
    Move multiple servos smoothly toward their targets simultaneously.

    angles_dict: {channel: (direction, target_angle)}
    current_angles: {channel: current_angle}
    """
    max_steps = 0
    for ch, (_, target) in angles_dict.items():
        max_steps = max(max_steps, abs(target - current_angles[ch]))

    if max_steps == 0:
        return

    for step in range(0, max_steps + 1, MOVE_STEP):
        for ch, (direction, target) in angles_dict.items():
            start = current_angles[ch]
            if start == target:
                continue

            t = min(1.0, step / max_steps)
            new_angle = int(start + (target - start) * t)
            set_servo_angle(ch, direction, new_angle)

        time.sleep(MOVE_DELAY)

    # Update final positions
    for ch, (_, target) in angles_dict.items():
        current_angles[ch] = target


def random_eye_position():
    """Return a random (x, y) coordinate within configured limits."""
    x = random.randint(*X_LIMITS)
    y = random.randint(*Y_LIMITS)
    return x, y


def blink_eyes():
    """
    Perform a coordinated blink on both eyes with optional side delay.
    """
    left_open = BLINK_OPEN_LEFT
    right_open = BLINK_OPEN_RIGHT
    closed = BLINK_LIMITS[1]

    left_range = closed - left_open
    right_range = closed - right_open
    steps_total = max(left_range, right_range)

    if steps_total <= 0:
        return

    # Convert side delay into step count
    side_steps = int(round(BLINK_SIDE_DELAY / BLINK_SPEED))

    # --- Closing phase ---
    for step in range(0, steps_total + 1):
        # Left progress
        left_progress = min(step, left_range) / left_range if left_range > 0 else 1.0
        left_angle = int(left_open + left_progress * left_range)

        # Right progress offset
        right_step_index = max(0, step - side_steps)
        right_progress = min(right_step_index, right_range) / right_range if right_range > 0 else 1.0
        right_angle = int(right_open + right_progress * right_range)

        set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, left_angle)
        set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, right_angle)

        time.sleep(BLINK_SPEED)

    # Closed duration
    time.sleep(BLINK_HOLD)

    # --- Opening phase ---
    for step in range(steps_total, -1, -1):
        left_progress = min(step, left_range) / left_range if left_range > 0 else 1.0
        left_angle = int(left_open + left_progress * left_range)

        right_step_index = max(0, step - side_steps)
        right_progress = min(right_step_index, right_range) / right_range if right_range > 0 else 1.0
        right_angle = int(right_open + right_progress * right_range)

        set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, left_angle)
        set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, right_angle)

        time.sleep(BLINK_SPEED)


def wait_for_enter():
    """Block until user presses Enter to continue."""
    print("⚙️ Eyes centered. Press [Enter] to start animation...")
    input()


# =====================================================
# INITIALIZATION
# =====================================================

neutral_x = (X_LIMITS[0] + X_LIMITS[1]) // 2
neutral_y = (Y_LIMITS[0] + Y_LIMITS[1]) // 2
left_blink_open = BLINK_OPEN_LEFT
right_blink_open = BLINK_OPEN_RIGHT

current_angles = {
    LEFT_X: neutral_x,
    LEFT_Y: neutral_y,
    LEFT_BLINK: left_blink_open,
    RIGHT_X: neutral_x,
    RIGHT_Y: neutral_y,
    RIGHT_BLINK: right_blink_open,
}

# Move servos to initial positions
set_servo_angle(LEFT_X, DIR_LEFT_X, neutral_x)
set_servo_angle(LEFT_Y, DIR_LEFT_Y, neutral_y)
set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, left_blink_open)
set_servo_angle(RIGHT_X, DIR_RIGHT_X, neutral_x)
set_servo_angle(RIGHT_Y, DIR_RIGHT_Y, neutral_y)
set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, right_blink_open)

wait_for_enter()

next_blink_time = time.time() + random.uniform(*BLINK_INTERVAL)
print("👁️  Animatronic eyes running — press Ctrl+C to stop")


# =====================================================
# MAIN LOOP
# =====================================================

try:
    while True:
        # Pick a new random target position
        new_x, new_y = random_eye_position()

        targets = {
            LEFT_X: (DIR_LEFT_X, new_x),
            LEFT_Y: (DIR_LEFT_Y, new_y),
            RIGHT_X: (DIR_RIGHT_X, new_x),
            RIGHT_Y: (DIR_RIGHT_Y, new_y),
        }

        move_servos_together(targets, current_angles)

        # Auto-blink
        if time.time() >= next_blink_time:
            blink_eyes()
            next_blink_time = time.time() + random.uniform(*BLINK_INTERVAL)

        time.sleep(random.uniform(0.5, 2.0))

except KeyboardInterrupt:
    pca.deinit()
    print("\n👋 Program stopped.")
