# Animatronic AI Chatbot

*A Raspberry Pi–powered AI chatbot with animatronic eyes, voice recognition, and an expressive LED mouth animation.*

👉 **Full build guide, detailed wiring, 3D printing, and explanation are available on my blog here:**  
**https://www.the-diy-life.com/i-built-a-pi-5-ai-chatbot-that-talks-blinks-and-looks-around/**

This repository contains two versions of code;

- **AIChatbot.py** — Full AI Chatbot Code which handles speech recognition, voice output, OpenAI responses, emotion colouring, LED mouth animation.
- **EyeMovement.py** — Just controls the animatronic eye servos, idle motion, blinking, and coordinated gaze movement. Doesn't have any chatbot functionality.

Use this repository together with the build instructions on my blog to assemble the animatronic eye mechanism and connect everything to the Raspberry Pi.

## 1. Hardware Setup

The physical assembly instructions for the animatronic eyes, servo mounts, wiring diagrams, and LED placement are available on my blog, linked at the begining. 

**Hardware used:**

- Raspberry Pi (Pi 5 recommended)  
- USB microphone  
- Speaker or I2S audio card  
- 4× micro servos for eyes  
- 2× micro servo for eyelids
- NeoPixel / WS2812B LED strip for mouth  

## 2. Software Setup

Follow these steps to get the software running.

### 2.1 Create and Activate a Python Virtual Environment

Pi OS Bookworm requires virtual environments for most GPIO + audio libraries.

```bash
sudo apt update
sudo apt install python3-venv python3-dev git -y

# Create virtual environment
python3 -m venv pica-env

# Activate environment
source pica-env/bin/activate
```

### 2.2 Install Required Python Libraries

Install dependencies inside the virtual environment:

```bash
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
    pygame \
    pyaudio \
    python-dotenv \
```

### 2.3 Setting Up OpenAI API

#### 2.3.1 Generate an API Key

1. Go to OpenAI Platform
2. Log in
3. Navigate to Dashboard → API Keys
4. Create a new API key
5. Copy the key

#### 2.3.2 Save the Key on Your Raspberry Pi

Create a .env file in your project directory:
```bash
nano .env
```
Add the following line:
```bash
OPENAI_API_KEY=your_api_key_here
```
Your AIChatbot.py file will automatically load this using dotenv.

## 3. Running the Code

### 3.1 Run Only the Eye Controller (for Testing)

```bash
python EyeMovement.py
```

### 3.2 Run the Chatbot

```bash
python AIChatbot.py
```

## 4. Customising Your AI Chatbot

### 4.1 Changing the Voice

In AIChatbot.py, locate the voice setting near the top:

```python
voice_name = "echo"
```

Replace "alloy" with any supported OpenAI TTS voice, for example:

```python
voice_name = "verse"
voice_name = "nova"
voice_name = "shimmer"
```

### 4.2 Changing the Personality

Find the system prompt in AIChatbot.py:

```python
  messages=[
    {"role": "system", "content": (
    "You are a calm, expressive AI. "
    "Respond concisely in 1 sentence unless necessary. "
    "Also output emotion as one of: happy, sad, neutral, angry, surprised. "
    "Format: <text> [emotion: <label>]"
  )},
```

Edit this text to change the AI's personality, style, and behaviour.

### 4.3 Adjusting Emotion Colours

The emotion-to-colour mapping is stored as:

```python
EMOTION_COLORS = {
  "happy": (0, 255, 255),      # yellow-ish
  "sad": (255, 0, 0),          # blue
  "angry": (0, 255, 0),        # red
  "surprised": (255, 255, 0),  # purple
  "neutral": (0, 255, 0),      # default green
}
```
Adjust any RGB combination as desired.
