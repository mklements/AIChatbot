# AIChatbot

A Raspberry Pi–powered AI character with animatronic eyes, voice recognition, and expressive LED mouth animation.

Full build guide, detailed wiring, 3D printing, and explanation are available on my blog here:
[PLACEHOLDER]

This repository contains the software that runs the animatronic system, including:

AIChatbot.py — Handles speech recognition, voice output, OpenAI responses, emotion colouring, LED mouth animation, button interaction, and more.

EyeMovement.py — Controls the animatronic eye servos, idle motion, blinking, and coordinated gaze movement.

Use this repository together with the build instructions on the blog to assemble the animatronic eye mechanism and connect everything to the Raspberry Pi.

⭐ Features

Real-time voice interaction powered by OpenAI

Animatronic eyes with smooth tracking and blinking

LED mouth bargraph synced to speech

Emotion-based colour themes

Wake-button activation

Customisable voice + personality

Fully runnable on Raspberry Pi 5 (Bookworm / PiOS 2025)

1. Hardware Setup

The physical assembly instructions for the animatronic eyes, servo mounts, wiring diagrams, and LED placement are all available here:

👉 [PLACEHOLDER – INSERT BLOG LINK TO BUILD GUIDE]

Hardware used:

Raspberry Pi (Pi 5 recommended)

USB microphone

Speaker or I2S audio card

2× micro servos for eyes

1× micro servo for eyelids (optional)

NeoPixel / WS2812B LED strip for mouth

Momentary button for wake activation

2. Software Setup

Below are the steps to get everything running on the Raspberry Pi.

2.1 Create and Activate a Python Virtual Environment

Bookworm/PiOS now requires virtual environments for most GPIO + audio libraries.

sudo apt update
sudo apt install python3-venv python3-dev git -y

# Create virtual environment
python3 -m venv pica-env

# Activate
source pica-env/bin/activate


Every time you run the program:

source pica-env/bin/activate

2.2 Install Required Python Libraries

Inside the virtual environment, install all dependencies:

pip install \
    openai \
    sounddevice \
    numpy \
    scipy \
    RPi.GPIO \
    gpiozero \
    adafruit-circuitpython-neopixel \
    adafruit-circuitpython-servokit \
    adafruit-circuitpython-ads1x15 \
    adafruit-circuitpython-pixelbuf \
    adafruit-circuitpython-led-animation \
    pillow \
    flask \
    python-dotenv \
    pydub \
    pygame


(Your exact library set may vary based on your final code — adjust as needed.)

3. Setting Up OpenAI API Access
3.1 Generate an API Key

Go to https://platform.openai.com

Log in

Go to Dashboard → API Keys

Create a new API key

Copy it

3.2 Save the Key on Your Raspberry Pi

Create a .env file in your project directory:

nano .env


Add:

OPENAI_API_KEY=your_api_key_here


Save and exit.

Your AIChatbot.py file loads this automatically using dotenv.

4. Running the Programs
Start the chatbot:
python AIChatbot.py

Run only the eye controller (for testing):
python EyeMovement.py

5. Customising Your AI Chatbot

One of the main features of this project is how easily you can change:

Voice style

Personality

Emotion behaviour

Speaking patterns

5.1 Changing the Voice

Inside AIChatbot.py, look for the section like:

voice_name = "alloy"


You can replace "alloy" with any supported OpenAI TTS voice.

Example:

voice_name = "verse"
voice_name = "nova"
voice_name = "shimmer"


(See the OpenAI voice catalog for the latest available voices.)

5.2 Changing the Personality

In the same file, find the system prompt:

SYSTEM_PROMPT = """
You are Whisplay, a friendly animatronic assistant...
"""


Edit this to whatever personality you want, for example:

Hyperactive robot

Calm storyteller

Sarcastic personality

Kid-friendly helper

Movie character style (while avoiding trademarked phrases)

You can also add rules such as:

speaking style

emotional ranges

how expressive the mouth animation should be

what the eyes do during speaking or thinking

5.3 Adjusting Emotion Colours

The emotion-to-colour mapping is usually stored like:

EMOTION_COLORS = {
    "happy": (0, 255, 100),
    "sad": (0, 50, 255),
    ...
}


Modify any RGB/BGR tuple you like.

If your strip uses BGR (common on Pi 5):

(brightness_blue, brightness_red, brightness_green)

5.4 Adjust Voice Speed / Pitch

Where speech is synthesised:

speech = client.audio.speech.create(
    model="gpt-4o-mini-tts",
    voice=voice_name,
    speed=1.0,
)


Adjust:

speed=0.8 → slower

speed=1.2 → faster

Some models also support pitch control.
