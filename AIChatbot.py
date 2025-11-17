import os
import time
import random
import threading
import wave
import pyaudio
import numpy as np
import audioop
import subprocess
import re

from openai import OpenAI

import board
import busio
from adafruit_pca9685 import PCA9685

# NeoPixel setup
import adafruit_pixelbuf
from adafruit_raspberry_pi5_neopixel_write import neopixel_write


# ================================================================
#  OPENAI CONFIGURATION
# ================================================================

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CHAT_MODEL = "gpt-4o-mini"
TTS_MODEL = "gpt-4o-mini-tts"
VOICE_NAME = "echo"


# ================================================================
#  SERVO / EYE CONFIGURATION
# ================================================================

i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# Servo channel mapping
LEFT_X, LEFT_Y, LEFT_BLINK = 0, 1, 2
RIGHT_X, RIGHT_Y, RIGHT_BLINK = 3, 4, 5

# Movement limits
X_LIMITS = (70, 110)
Y_LIMITS = (70, 110)
BLINK_LIMITS = (0, 40)

# Servo directions
DIR_LEFT_X = 1
DIR_LEFT_Y = 1
DIR_LEFT_BLINK = 1

DIR_RIGHT_X = 1
DIR_RIGHT_Y = -1
DIR_RIGHT_BLINK = -1

# Blink configuration
BLINK_OPEN_LEFT = -12
BLINK_OPEN_RIGHT = 0
BLINK_SIDE_DELAY = 0.03

MOVE_STEP = 1
MOVE_DELAY = 0.01
BLINK_INTERVAL = (7, 12)
BLINK_SPEED = 0.003
BLINK_HOLD = 0.10

last_blink_timestamp = 0.0

# Servo pulse widths
MIN_PULSE_MS = 0.5
MAX_PULSE_MS = 2.5
PERIOD_MS = 20.0

# Mouth smoothing factor
MOUTH_SMOOTHING = 0.6  # 0 = jumpy, 1 = smooth
previous_audio_level = 0.0

# Global state flags
is_running = True
is_speaking = False
is_thinking = False

# Track servo angles
current_servo_angles = {}


# ================================================================
#  NEOPIXEL MOUTH CONFIGURATION
# ================================================================

NEOPIXEL_PIN = board.D13
NUM_PIXELS = 8


class Pi5PixelBuf(adafruit_pixelbuf.PixelBuf):
    """Custom PixelBuf implementation for Raspberry Pi 5."""

    def __init__(self, pin, size, **kwargs):
        self._pin = pin
        super().__init__(size=size, **kwargs)

    def _transmit(self, buf):
        neopixel_write(self._pin, buf)


pixels = Pi5PixelBuf(NEOPIXEL_PIN, NUM_PIXELS, auto_write=True, byteorder="BGR")


def show_mouth(amplitude, color=(0, 0, 255)):
    """Display mouth levels symmetrically based on amplitude."""
    amplitude = max(0.0, min(1.0, amplitude))
    num_lit = int(round(amplitude * NUM_PIXELS))

    pixels.fill((0, 0, 0))

    center_left = NUM_PIXELS // 2 - 1
    center_right = NUM_PIXELS // 2

    for i in range(num_lit // 2):
        left_pos = center_left - i
        right_pos = center_right + i

        if 0 <= left_pos < NUM_PIXELS:
            pixels[left_pos] = color
        if 0 <= right_pos < NUM_PIXELS:
            pixels[right_pos] = color

    pixels.show()


def clear_mouth():
    """Turn off all mouth LEDs."""
    pixels.fill((0, 0, 0))
    pixels.show()


# ================================================================
#  SERVO + EYE CONTROL
# ================================================================

def set_servo_angle(channel, direction, angle):
    """Send corrected angle to PCA9685 servo."""
    if direction == -1:
        angle = 180 - angle

    pulse_range = MAX_PULSE_MS - MIN_PULSE_MS
    pulse_width = MIN_PULSE_MS + (pulse_range * angle / 180.0)
    duty_cycle = int((pulse_width / PERIOD_MS) * 65535)

    pca.channels[channel].duty_cycle = duty_cycle


def move_servos_together(angle_targets, current_angles):
    """Smoothly move several servos together."""
    max_steps = 0
    for ch, (_, target) in angle_targets.items():
        max_steps = max(max_steps, abs(target - current_angles.get(ch, target)))

    if max_steps == 0:
        return

    for step in range(0, max_steps + 1, MOVE_STEP):
        for ch, (direction, target) in angle_targets.items():
            start = current_angles.get(ch, target)
            if start == target:
                continue

            t = min(1.0, step / max_steps)
            new_angle = int(start + (target - start) * t)

            set_servo_angle(ch, direction, new_angle)

        time.sleep(MOVE_DELAY)

    for ch, (_, target) in angle_targets.items():
        current_angles[ch] = target


def random_eye_position(scale=1.0):
    """Generate random eye coordinates."""
    x_mid = (X_LIMITS[0] + X_LIMITS[1]) // 2
    y_mid = (Y_LIMITS[0] + Y_LIMITS[1]) // 2

    x_radius = int((X_LIMITS[1] - X_LIMITS[0]) / 2 * scale)
    y_radius = int((Y_LIMITS[1] - Y_LIMITS[0]) / 2 * scale)

    x = random.randint(x_mid - x_radius, x_mid + x_radius)
    y = random.randint(y_mid - y_radius, y_mid + y_radius)

    return x, y


def blink_eyes(probability=1.0):
    """Full natural blink with staggered eyelid motion."""
    if random.random() > probability:
        return

    left_open = BLINK_OPEN_LEFT
    right_open = BLINK_OPEN_RIGHT
    closed = BLINK_LIMITS[1]

    left_range = closed - left_open
    right_range = closed - right_open

    steps_total = max(left_range, right_range)
    if steps_total <= 0:
        return

    side_offset_steps = int(round(BLINK_SIDE_DELAY / BLINK_SPEED))

    # Closing motion
    for step in range(0, steps_total + 1):
        left_progress = min(step, left_range) / left_range if left_range > 0 else 1.0

        right_step_corrected = max(0, step - side_offset_steps)
        right_progress = min(right_step_corrected, right_range) / right_range if right_range > 0 else 1.0

        left_angle = int(left_open + left_progress * left_range)
        right_angle = int(right_open + right_progress * right_range)

        set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, left_angle)
        set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, right_angle)

        time.sleep(BLINK_SPEED)

    time.sleep(BLINK_HOLD)

    # Opening motion
    for step in range(steps_total, -1, -1):
        left_progress = min(step, left_range) / left_range if left_range > 0 else 1.0

        right_step_corrected = max(0, step - side_offset_steps)
        right_progress = min(right_step_corrected, right_range) / right_range if right_range > 0 else 1.0

        left_angle = int(left_open + left_progress * left_range)
        right_angle = int(right_open + right_progress * right_range)

        set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, left_angle)
        set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, right_angle)

        time.sleep(BLINK_SPEED)


def wink():
    """Random single-eye wink."""
    global last_blink_timestamp

    last_blink_timestamp = time.time()
    chosen_side = random.choice(["left", "right"])

    left_open = BLINK_OPEN_LEFT
    right_open = BLINK_OPEN_RIGHT
    closed = BLINK_LIMITS[1]

    steps = abs(closed - left_open)

    # LEFT wink
    if chosen_side == "left":
        for step in range(steps + 1):
            angle = int(left_open + (closed - left_open) * (step / steps))
            set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, angle)
            time.sleep(BLINK_SPEED)

        time.sleep(BLINK_HOLD)

        for step in range(steps, -1, -1):
            angle = int(left_open + (closed - left_open) * (step / steps))
            set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, angle)
            time.sleep(BLINK_SPEED)

    else:  # RIGHT wink
        for step in range(steps + 1):
            angle = int(right_open + (closed - right_open) * (step / steps))
            set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, angle)
            time.sleep(BLINK_SPEED)

        time.sleep(BLINK_HOLD)

        for step in range(steps, -1, -1):
            angle = int(right_open + (closed - right_open) * (step / steps))
            set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, angle)
            time.sleep(BLINK_SPEED)

    last_blink_timestamp = time.time()


def blink_twice():
    """Double blink."""
    global last_blink_timestamp

    for _ in range(2):
        blink_eyes(probability=1.0)
        last_blink_timestamp = time.time()
        time.sleep(0.3)


def eyes_idle_loop():
    """Background idle movement and blinking for eyes."""
    global is_running, is_speaking, is_thinking, last_blink_timestamp

    next_blink = time.time() + random.uniform(*BLINK_INTERVAL)

    while is_running:
        now = time.time()

        # THINKING MODE
        if is_thinking:
            for _ in range(2):
                new_x, new_y = random_eye_position(scale=0.5)
                targets = {
                    LEFT_X: (DIR_LEFT_X, new_x),
                    LEFT_Y: (DIR_LEFT_Y, new_y),
                    RIGHT_X: (DIR_RIGHT_X, new_x),
                    RIGHT_Y: (DIR_RIGHT_Y, new_y)
                }

                move_servos_together(targets, current_servo_angles)

                if random.random() < 0.3 and now - last_blink_timestamp > 0.2:
                    blink_eyes(probability=1.0)
                    last_blink_timestamp = time.time()

                time.sleep(1)

        # SPEAKING MODE
        elif is_speaking:
            new_x, new_y = random_eye_position(scale=0.3)
            targets = {
                LEFT_X: (DIR_LEFT_X, new_x),
                LEFT_Y: (DIR_LEFT_Y, new_y),
                RIGHT_X: (DIR_RIGHT_X, new_x),
                RIGHT_Y: (DIR_RIGHT_Y, new_y)
            }

            move_servos_together(targets, current_servo_angles)

            if random.random() < 0.2 and now - last_blink_timestamp > 0.2:
                blink_eyes(probability=1.0)
                last_blink_timestamp = time.time()

            time.sleep(random.uniform(0.8, 1.8))

        # IDLE MODE
        else:
            new_x, new_y = random_eye_position(scale=1.0)
            targets = {
                LEFT_X: (DIR_LEFT_X, new_x),
                LEFT_Y: (DIR_LEFT_Y, new_y),
                RIGHT_X: (DIR_RIGHT_X, new_x),
                RIGHT_Y: (DIR_RIGHT_Y, new_y)
            }

            move_servos_together(targets, current_servo_angles)

            if now >= next_blink:
                blink_eyes(probability=1.0)
                last_blink_timestamp = time.time()
                next_blink = time.time() + random.uniform(*BLINK_INTERVAL)

            time.sleep(random.uniform(1, 3))


def center_eyes():
    """Move eyes and eyelids to neutral center positions."""
    neutral_x = (X_LIMITS[0] + X_LIMITS[1]) // 2
    neutral_y = (Y_LIMITS[0] + Y_LIMITS[1]) // 2

    left_blink_open = BLINK_OPEN_LEFT
    right_blink_open = BLINK_OPEN_RIGHT

    current_servo_angles.update({
        LEFT_X: neutral_x,
        LEFT_Y: neutral_y,
        LEFT_BLINK: left_blink_open,
        RIGHT_X: neutral_x,
        RIGHT_Y: neutral_y,
        RIGHT_BLINK: right_blink_open
    })

    set_servo_angle(LEFT_X, DIR_LEFT_X, neutral_x)
    set_servo_angle(LEFT_Y, DIR_LEFT_Y, neutral_y)
    set_servo_angle(LEFT_BLINK, DIR_LEFT_BLINK, left_blink_open)

    set_servo_angle(RIGHT_X, DIR_RIGHT_X, neutral_x)
    set_servo_angle(RIGHT_Y, DIR_RIGHT_Y, neutral_y)
    set_servo_angle(RIGHT_BLINK, DIR_RIGHT_BLINK, right_blink_open)


# ================================================================
#  AUDIO RECORDING + TRANSCRIPTION
# ================================================================

def record_audio(filename="input.wav", threshold=500, silence_duration=1.5):
    """
    Voice-activated audio recorder:
    Starts recording when volume > threshold,
    stops after silence_duration seconds of silence.
    """
    audio_interface = pyaudio.PyAudio()

    stream = audio_interface.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1024
    )

    print("🎤 Listening for speech...")

    frames = []
    recording_started = False
    silence_start_time = None

    try:
        while True:
            data = stream.read(1024, exception_on_overflow=False)
            rms = audioop.rms(data, 2)

            if recording_started:
                frames.append(data)

                if rms < threshold:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif time.time() - silence_start_time >= silence_duration:
                        break
                else:
                    silence_start_time = None
            else:
                if rms >= threshold:
                    recording_started = True
                    print("🛑 Recording started!")
                    frames.append(data)

    except KeyboardInterrupt:
        print("\n🛑 Recording interrupted.")

    print("🛑 Finished recording.")

    stream.stop_stream()
    stream.close()
    audio_interface.terminate()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio_interface.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b"".join(frames))

    return filename


def transcribe_audio(filename):
    """Use Whisper API to convert audio to text."""
    print("🧠 Transcribing...")

    with open(filename, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

    return result.text.strip()


# ================================================================
#  SPEECH SYNTHESIS + MOUTH MOVEMENT
# ================================================================

def speak_text(text, color=(0, 0, 255)):
    """Speak via TTS and animate mouth with amplitude levels."""
    global is_speaking, previous_audio_level

    is_speaking = True

    mp3_path = "speech_output.mp3"
    wav_path = "speech_output.wav"

    # Generate TTS
    with client.audio.speech.with_streaming_response.create(
        model=TTS_MODEL,
        voice=VOICE_NAME,
        input=text
    ) as response:
        response.stream_to_file(mp3_path)

    # Convert to mono WAV
    subprocess.run(
        ["ffmpeg", "-y", "-i", mp3_path, "-ac", "1", "-ar", "16000", wav_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    wave_file = wave.open(wav_path, 'rb')
    audio_interface = pyaudio.PyAudio()

    output_stream = audio_interface.open(
        format=audio_interface.get_format_from_width(wave_file.getsampwidth()),
        channels=wave_file.getnchannels(),
        rate=wave_file.getframerate(),
        output=True
    )

    chunk_size = 512
    audio_playback_delay = 0.07  # lip-sync correction

    data = wave_file.readframes(chunk_size)
    playback_start_time = time.time() + audio_playback_delay

    while data:
        rms = audioop.rms(data, 2) / 32768.0
        level = min(1.0, np.log10(1 + 55 * rms))

        level = (
            MOUTH_SMOOTHING * previous_audio_level +
            (1 - MOUTH_SMOOTHING) * level
        )

        previous_audio_level = level

        show_mouth(level, color=color)

        while time.time() < playback_start_time:
            pass

        output_stream.write(data)
        playback_start_time += chunk_size / wave_file.getframerate()

        data = wave_file.readframes(chunk_size)

    clear_mouth()
    output_stream.stop_stream()
    output_stream.close()
    audio_interface.terminate()
    wave_file.close()

    os.remove(mp3_path)
    os.remove(wav_path)

    is_speaking = False


# ================================================================
#  MAIN LOOP + EMOTION PROCESSING
# ================================================================

def main():
    global is_running, is_thinking, last_blink_timestamp

    center_eyes()
    clear_mouth()

    print("🤖 Animatronic Chatbot Ready.")
    input("Press ENTER to begin...")

    eye_thread = threading.Thread(target=eyes_idle_loop)
    eye_thread.start()

    try:
        while True:
            audio_path = record_audio()

            is_thinking = True
            user_text = transcribe_audio(audio_path)

            print(f"🧑 You said: {user_text}")

            os.remove(audio_path)
            norm = user_text.lower().strip()

            # ----------------------------------------------
            # Easter eggs
            # ----------------------------------------------
            if "wink for me" in norm or norm.startswith("wink") or "can you wink" in norm:
                is_thinking = False
                print("✨ Easter Egg: wink")
                wink()
                continue

            if "blink twice" in norm and "understand" in norm:
                is_thinking = False
                print("✨ Easter Egg: blink twice")
                blink_twice()
                continue

            # ----------------------------------------------
            # Exit commands
            # ----------------------------------------------
            if norm in ["quit", "exit", "stop"]:
                is_running = False
                pca.deinit()
                clear_mouth()
                print("👋 Goodbye.")
                break

            # ----------------------------------------------
            # Normal conversation
            # ----------------------------------------------
            print("🤔 Thinking...")

            response = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are a calm, expressive AI. "
                        "Respond concisely in 1 sentence unless necessary. "
                        "Also output emotion as one of: happy, sad, neutral, angry, surprised. "
                        "Format: <text> [emotion: <label>]"
                    )},
                    {"role": "user", "content": user_text},
                ]
            )

            full_reply = response.choices[0].message.content.strip()

            # Extract emotion
            match = re.search(r"\[emotion:\s*(\w+)\]", full_reply, re.IGNORECASE)
            emotion = match.group(1).lower() if match else "neutral"

            # Strip label before TTS
            reply_text = re.sub(r"\[emotion:.*\]", "", full_reply).strip()

            EMOTION_COLORS = {
                "happy": (0, 255, 255),      # yellow-ish
                "sad": (255, 0, 0),          # blue
                "angry": (0, 255, 0),        # red
                "surprised": (255, 255, 0),  # purple
                "neutral": (0, 255, 0),      # default green
            }

            color = EMOTION_COLORS.get(emotion, (0, 255, 0))

            is_thinking = False

            print(f"🤖 {reply_text}  [{emotion}]")
            speak_text(reply_text, color=color)

    except KeyboardInterrupt:
        is_running = False
        pca.deinit()
        clear_mouth()
        print("\n👋 Program stopped.")


if __name__ == "__main__":
    main()
