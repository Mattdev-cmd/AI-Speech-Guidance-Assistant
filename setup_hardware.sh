#!/bin/bash
# ============================================================
# Hardware Setup Script for the Speech Guidance Self-Assistant
# Target: Raspberry Pi 4 + ReSpeaker 2-Mics Pi HAT v2.0
#         + Raspberry Pi Camera Rev 1.3
# Run: sudo bash setup_hardware.sh
# ============================================================

set -e

echo "============================================="
echo " Speech Guidance Assistant - Hardware Setup"
echo "============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash setup_hardware.sh)"
    exit 1
fi

# Detect user (for non-root operations later)
ACTUAL_USER=${SUDO_USER:-$USER}
echo "Setting up for user: $ACTUAL_USER"
echo ""

# ─── 1. System Update ────────────────────────────

echo "[1/7] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
echo "  ✓ System updated"

# ─── 2. Install System Dependencies ──────────────

echo "[2/7] Installing system dependencies..."
apt-get install -y -qq \
    python3-pip python3-venv python3-dev \
    portaudio19-dev \
    libatlas-base-dev \
    libopenblas-dev \
    ffmpeg \
    mpg123 \
    i2c-tools \
    libcamera-dev \
    python3-libcamera python3-picamera2 \
    git \
    espeak \
    libasound2-dev
echo "  ✓ System dependencies installed"

# ─── 3. Enable Interfaces ────────────────────────

echo "[3/7] Enabling hardware interfaces..."

# Enable I2C (used by ReSpeaker)
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
    echo "  Added I2C to config.txt"
fi

# Enable SPI (used by ReSpeaker LEDs)
if ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtparam=spi=on" >> /boot/firmware/config.txt
    echo "  Added SPI to config.txt"
fi

# Enable Camera
if ! grep -q "^start_x=1" /boot/firmware/config.txt 2>/dev/null; then
    echo "start_x=1" >> /boot/firmware/config.txt
    echo "gpu_mem=128" >> /boot/firmware/config.txt
    echo "  Added camera settings to config.txt"
fi

echo "  ✓ Hardware interfaces enabled"

# ─── 4. Install ReSpeaker 2-Mics Pi HAT Driver ──

echo "[4/7] Installing ReSpeaker 2-Mics Pi HAT v2.0 driver..."

RESPEAKER_DIR="/tmp/seeed-voicecard"
if [ -d "$RESPEAKER_DIR" ]; then
    rm -rf "$RESPEAKER_DIR"
fi

git clone --depth 1 https://github.com/HinTak/seeed-voicecard.git "$RESPEAKER_DIR"
cd "$RESPEAKER_DIR"

# Install the driver
./install.sh
cd -

echo "  ✓ ReSpeaker driver installed"

# ─── 5. Configure Audio ──────────────────────────

echo "[5/7] Configuring audio..."

# Create ALSA config for ReSpeaker as default
cat > /home/$ACTUAL_USER/.asoundrc << 'EOF'
pcm.!default {
    type asym
    playback.pcm "plughw:seeed2micvoicec"
    capture.pcm "plughw:seeed2micvoicec"
}
ctl.!default {
    type hw
    card seeed2micvoicec
}
EOF
chown $ACTUAL_USER:$ACTUAL_USER /home/$ACTUAL_USER/.asoundrc

echo "  ✓ Audio configured (ReSpeaker as default)"

# ─── 6. Python Virtual Environment & Packages ────

echo "[6/7] Setting up Python environment..."

PROJECT_DIR="/home/$ACTUAL_USER/speech-guidance-assistant"
if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p "$PROJECT_DIR"
fi

# Create virtual environment
sudo -u $ACTUAL_USER python3 -m venv "$PROJECT_DIR/venv" --system-site-packages

# Install Python packages
sudo -u $ACTUAL_USER "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
sudo -u $ACTUAL_USER "$PROJECT_DIR/venv/bin/pip" install \
    PyYAML numpy pyaudio webrtcvad sounddevice \
    openai-whisper SpeechRecognition \
    ollama openai \
    pyttsx3 gTTS \
    spidev gpiod \
    flask flask-socketio \
    Pillow requests

echo "  ✓ Python environment ready"

# ─── 7. Install Ollama (Local LLM) ───────────────

echo "[7/7] Installing Ollama for local AI..."

if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.ai/install.sh | sh
    echo "  ✓ Ollama installed"
else
    echo "  ✓ Ollama already installed"
fi

# Pull the recommended model
echo "  Pulling llama3.2:3b model (this may take a while)..."
sudo -u $ACTUAL_USER ollama pull llama3.2:3b
echo "  ✓ AI model downloaded"

# ─── Done ─────────────────────────────────────────

echo ""
echo "============================================="
echo " Setup Complete!"
echo "============================================="
echo ""
echo " Next steps:"
echo "   1. Reboot:  sudo reboot"
echo "   2. After reboot, navigate to your project:"
echo "      cd $PROJECT_DIR"
echo "   3. Activate virtual environment:"
echo "      source venv/bin/activate"
echo "   4. Copy project files to $PROJECT_DIR"
echo "   5. Run the assistant:"
echo "      python main.py"
echo ""
echo " Optional:"
echo "   - Web dashboard: python main.py --mode web"
echo "   - Without camera: python main.py --no-camera"
echo "   - Test audio: arecord -D plughw:seeed2micvoicec -f S16_LE -r 16000 -c 1 test.wav"
echo "   - Test camera: libcamera-still -o test.jpg"
echo ""
echo " Hardware checklist:"
echo "   □ ReSpeaker 2-Mics Pi HAT seated on GPIO pins"
echo "   □ Pi Camera ribbon cable connected (silver contacts facing PCB)"
echo "   □ Speaker connected to ReSpeaker 3.5mm jack or JST port"
echo ""
