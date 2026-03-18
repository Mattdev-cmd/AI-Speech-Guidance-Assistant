# AI-Powered Speech Guidance Self-Assistant

A real-time speech guidance system that listens to your conversations, transcribes speech, and provides AI-generated response suggestions — all running on a Raspberry Pi 4.

## Hardware

| Component | Model |
|---|---|
| Computer | Raspberry Pi 4 (4GB+ recommended) |
| Microphone | ReSpeaker 2-Mics Pi HAT v2.0 |
| Camera | Raspberry Pi Camera Rev 1.3 |
| Speaker | Any 3.5mm or JST speaker (via ReSpeaker) |
| Display | HDMI monitor, terminal, or web browser |

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  ReSpeaker   │───▶│  Speech-to-  │───▶│  AI Engine   │
│  2-Mics HAT  │    │  Text (STT)  │    │  (Ollama /   │
│  + VAD       │    │  Whisper     │    │   OpenAI)    │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
┌──────────────┐    ┌──────────────┐    ┌──────▼───────┐
│  Pi Camera   │───▶│  Scene       │───▶│  Response    │
│  Rev 1.3     │    │  Analysis    │    │  Suggestions │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
                    ┌──────────────┐    ┌──────▼───────┐
                    │  Text-to-    │◀───│  Display     │
                    │  Speech      │    │  (Terminal / │
                    │  (pyttsx3)   │    │   Web / HDMI)│
                    └──────────────┘    └──────────────┘
                           │
                    ┌──────▼───────┐
                    │  ReSpeaker   │
                    │  Speaker Out │
                    └──────────────┘
```

## How It Works

1. **Listen** — The ReSpeaker 2-Mics Pi HAT captures audio with Voice Activity Detection (VAD)
2. **Transcribe** — Speech is converted to text using Whisper (local) or Google STT
3. **See** — The Pi Camera captures the scene for visual context (optional)
4. **Think** — An LLM (local Ollama or cloud OpenAI) analyzes the transcript + scene
5. **Suggest** — 2-3 response suggestions are displayed with contextual guidance
6. **Speak** — Guidance is optionally spoken aloud through the ReSpeaker speaker

## Quick Start

### 1. Hardware Assembly

```
Raspberry Pi Camera Rev 1.3
  └─ ribbon cable ─▶ Pi Camera CSI port

ReSpeaker 2-Mics Pi HAT v2.0
  └─ seated on ─▶ Pi 4 GPIO 40-pin header

Speaker
  └─ plugged into ─▶ ReSpeaker 3.5mm jack or JST connector
```

### 2. Software Setup

```bash
# Clone or copy project to the Pi
scp -r speech-guidance-assistant/ pi@raspberrypi.local:~/

# SSH into the Pi
ssh pi@raspberrypi.local

# Run hardware setup (installs drivers, dependencies, Ollama)
cd ~/speech-guidance-assistant
sudo bash setup_hardware.sh

# Reboot (required for ReSpeaker driver)
sudo reboot
```

### 3. Run the Assistant

```bash
cd ~/speech-guidance-assistant
source venv/bin/activate

# Terminal mode (default)
python main.py

# Web dashboard (access from any browser on your network)
python main.py --mode web
# Then open http://raspberrypi.local:8080

# Without camera
python main.py --no-camera

# With Google STT instead of Whisper
python main.py --stt-engine google
```

## Display Modes

### Terminal / HDMI
Rich colored text output showing:
- Your transcribed speech
- AI-generated response suggestions (numbered 1-3)
- Contextual guidance
- Scene descriptions from camera

### Web Dashboard
Real-time browser UI at `http://<pi-ip>:8080`:
- WebSocket-powered live updates
- Mobile-friendly responsive design
- Visual status indicators
- Works from any device on your network

## Configuration

Edit `config.yaml` to customize:

```yaml
# Switch AI provider
ai:
  provider: "ollama"          # "ollama" (local/private) or "openai" (cloud)
  ollama_model: "llama3.2:3b" # Smaller model for faster responses

# Adjust Whisper model size (speed vs accuracy tradeoff)
stt:
  whisper_model: "tiny"   # tiny (fastest) → base → small → medium → large (most accurate)

# Change display mode
display:
  mode: "web"     # "terminal", "web", or "hdmi"
  web_port: 8080

# Customize LED feedback colors
leds:
  listening_color: [0, 0, 255]
  processing_color: [255, 165, 0]
```

## LED Indicators (ReSpeaker HAT)

| Color | State |
|---|---|
| 🟢 Green | Ready / idle |
| 🔵 Blue | Listening for speech |
| 🟠 Orange (breathing) | Processing speech + generating suggestions |
| 🔴 Red | Error |

## Run as a System Service

To start the assistant automatically on boot:

```bash
# Copy service file
sudo cp speech-assistant.service /etc/systemd/system/

# Enable and start
sudo systemctl enable speech-assistant
sudo systemctl start speech-assistant

# Check status
sudo systemctl status speech-assistant

# View logs
journalctl -u speech-assistant -f
```

## Project Structure

```
speech-guidance-assistant/
├── main.py                  # Application entry point & orchestrator
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── setup_hardware.sh        # Hardware setup script (run once)
├── speech-assistant.service # systemd service file
├── modules/
│   ├── __init__.py
│   ├── audio_capture.py     # ReSpeaker mic input + VAD
│   ├── led_controller.py    # ReSpeaker APA102 LED control
│   ├── camera_module.py     # Pi Camera capture + scene frames
│   ├── speech_to_text.py    # Whisper / Google STT
│   ├── ai_engine.py         # LLM response generation
│   ├── text_to_speech.py    # pyttsx3 / gTTS audio output
│   └── display.py           # Terminal + Web dashboard UI
└── README.md
```

## Troubleshooting

### ReSpeaker not detected
```bash
# Check if driver loaded
arecord -l
# Should show "seeed2micvoicec"

# Reinstall driver if needed
cd /tmp/seeed-voicecard && sudo ./install.sh
sudo reboot
```

### Camera not working
```bash
# Test camera
libcamera-still -o test.jpg

# Check if enabled
vcgencmd get_camera
# Should show: supported=1 detected=1

# Verify ribbon cable: silver contacts face the PCB on both ends
```

### Ollama model not responding
```bash
# Check Ollama is running
systemctl status ollama

# Test directly
ollama run llama3.2:3b "Hello"

# Pull model if missing
ollama pull llama3.2:3b
```

### Audio playback issues
```bash
# Test speaker output
speaker-test -D plughw:seeed2micvoicec -c 1

# Adjust volume
alsamixer
```

## Performance Notes

| Whisper Model | RAM Usage | Transcription Speed (Pi 4) |
|---|---|---|
| tiny | ~1 GB | ~3x real-time |
| base | ~1 GB | ~1.5x real-time |
| small | ~2 GB | ~0.5x real-time |

- **Recommended**: `base` model for best balance on Pi 4 with 4GB RAM
- **Fastest**: `tiny` model if you need near-instant transcription
- Ollama `llama3.2:3b` uses ~2-3GB RAM — ensure Pi 4 has 4GB+ total

## License

MIT License — Free for personal and educational use.
