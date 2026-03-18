#!/usr/bin/env python3
"""
AI-Powered Speech Guidance Self-Assistant
==========================================
Main application entry point.

Hardware:
  - Raspberry Pi 4
  - ReSpeaker 2-Mics Pi HAT v2.0
  - Raspberry Pi Camera Rev 1.3

This assistant listens to your speech in real-time, transcribes it,
analyzes the context (with optional camera scene awareness), and
provides interactive response suggestions to guide your conversation.

NOW WITH STREAMING RESPONSES — See AI responses appear token-by-token!

Usage:
    python main.py                    # Run with default config
    python main.py --config my.yaml   # Run with custom config
    python main.py --mode web         # Run with web dashboard
    python main.py --no-camera        # Disable camera
"""

import argparse
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time

import yaml

from modules.audio_capture import AudioCapture
from modules.camera_module import CameraModule
from modules.speech_to_text import SpeechToText
from modules.ai_engine import AIResponseEngine
from modules.streaming_response import StreamingResponseHandler
from modules.text_to_speech import TextToSpeech
from modules.led_controller import LEDController
from modules.display import create_display

logger = logging.getLogger("assistant")


class SpeechGuidanceAssistant:
    """Main application orchestrator with streaming responses."""

    def __init__(self, config: dict):
        self.config = config
        self._running = False
        self._scene_description = ""
        self._scene_lock = threading.Lock()
        self._processing_lock = threading.Lock()

        # Initialize all modules
        logger.info("Initializing modules...")
        self.leds = LEDController(config)
        self.display = create_display(config)
        self.stt = SpeechToText(config)
        self.ai = AIResponseEngine(config)
        self.streaming = StreamingResponseHandler(config)  # NEW: Streaming handler
        self.tts = TextToSpeech(config)
        self.camera = CameraModule(config)
        self.audio = AudioCapture(config, on_speech_callback=self._on_speech_detected)

        # Scene analysis timer
        self._scene_interval = config.get("camera", {}).get("scene_analysis_interval", 10)
        self._scene_timer = None

        logger.info("All modules initialized successfully")

    def _on_speech_detected(self, audio_bytes: bytes):
        """Callback when a speech segment is detected by the audio module."""
        # Prevent concurrent processing
        if not self._processing_lock.acquire(blocking=False):
            logger.debug("Already processing, skipping segment")
            return

        try:
            self._process_speech(audio_bytes)
        finally:
            self._processing_lock.release()

    def _process_speech(self, audio_bytes: bytes):
        """Full pipeline: STT -> AI (STREAMING) -> Display -> TTS."""
        # 1. Indicate processing
        self.leds.breathe("processing")
        self.display.show_processing()

        # 2. Capture camera frame for context (if enabled)
        scene_desc = ""
        if self.camera.enabled and self.config.get("camera", {}).get("capture_on_speech", True):
            frame = self.camera.capture_for_analysis()
            if frame:
                scene_desc = self.ai.analyze_scene(frame)
                if scene_desc:
                    self.display.show_scene(scene_desc)

        # Use cached scene description as fallback
        if not scene_desc:
            with self._scene_lock:
                scene_desc = self._scene_description

        # 3. Transcribe speech
        transcript = self.stt.transcribe(audio_bytes)
        if not transcript:
            logger.info("No speech transcribed, returning to listening")
            self.leds.set_state("listening")
            self.display.show_listening()
            return

        # 4. Display transcript
        self.display.show_transcript_text(transcript)

        # 5. STREAM the AI response
        messages = [
            {"role": "system", "content": self.ai.system_prompt},
            {"role": "user", "content": transcript}
        ]

        if scene_desc:
            messages[-1]["content"] += f"\n[Scene context: {scene_desc}]"

        # Start streaming display
        self.display.stream_response_start("AI RESPONSE")

        # Collect full response while streaming tokens
        full_response = ""
        response_text = ""

        def on_token(token: str):
            nonlocal full_response, response_text
            full_response += token
            response_text += token
            self.display.stream_token(token)  # Display token in terminal

        def on_complete(response: str):
            self.display.stream_response_end()

        def on_error(error: str):
            logger.error("Streaming error: %s", error)

        # Stream response from LLM
        self.streaming.stream_response(
            messages,
            on_token=on_token,
            on_complete=on_complete,
            on_error=on_error
        )

        # 6. Speak the response (if enabled)
        if full_response:
            self.tts.speak_async(full_response)

        # 7. Return to listening state
        self.leds.set_state("listening")
        self.display.show_listening()

    def _periodic_scene_analysis(self):
        """Periodically analyze the scene for context updates."""
        if not self._running or not self.camera.enabled:
            return

        frame = self.camera.capture_for_analysis()
        if frame:
            desc = self.ai.analyze_scene(frame)
            if desc:
                with self._scene_lock:
                    self._scene_description = desc
                logger.debug("Periodic scene update: %s", desc[:60])

        # Schedule next analysis
        if self._running:
            self._scene_timer = threading.Timer(self._scene_interval, self._periodic_scene_analysis)
            self._scene_timer.daemon = True
            self._scene_timer.start()

    def start(self):
        """Start the assistant."""
        self._running = True

        # Show startup banner
        print("\n" + "=" * 60)
        print("  🎤 AI-Powered Speech Guidance Self-Assistant")
        print("  Hardware: RPi 4 + ReSpeaker 2-Mics + Pi Camera")
        print("=" * 60)
        print(f"  STT Engine:  {self.config.get('stt', {}).get('engine', 'whisper')}")
        print(f"  AI Provider: {self.config.get('ai', {}).get('provider', 'ollama')}")
        print(f"  Display:     {self.config.get('display', {}).get('mode', 'terminal')}")
        print(f"  Camera:      {'Enabled' if self.camera.enabled else 'Disabled'}")
        print("=" * 60 + "\n")

        # Start LED ready state
        self.leds.set_state("ready")
        time.sleep(1)

        # Start audio capture
        self.leds.set_state("listening")
        self.audio.start()
        self.display.show_listening()

        # Start periodic scene analysis
        if self.camera.enabled and self._scene_interval > 0:
            self._scene_timer = threading.Timer(2, self._periodic_scene_analysis)
            self._scene_timer.daemon = True
            self._scene_timer.start()

        logger.info("Assistant started and listening")

    def stop(self):
        """Gracefully stop the assistant."""
        logger.info("Shutting down assistant...")
        self._running = False

        if self._scene_timer:
            self._scene_timer.cancel()

        self.audio.cleanup()
        self.camera.cleanup()
        self.tts.cleanup()
        self.leds.cleanup()

        logger.info("Assistant stopped")
        print("\n👋 Assistant stopped. Goodbye!")


def setup_logging(config: dict):
    """Configure logging from the config file."""
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)

    # File handler with rotation
    log_file = log_cfg.get("file", "assistant.log")
    max_bytes = log_cfg.get("max_size_mb", 10) * 1024 * 1024
    backup_count = log_cfg.get("backup_count", 3)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)


def load_config(path: str) -> dict:
    """Load YAML configuration."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    logger.warning("Config file not found: %s, using defaults", path)
    return {}


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Speech Guidance Self-Assistant"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to configuration file"
    )
    parser.add_argument(
        "--mode",
        choices=["terminal", "web", "hdmi"],
        help="Display mode (overrides config)",
    )
    parser.add_argument(
        "--no-camera", action="store_true", help="Disable camera module"
    )
    parser.add_argument(
        "--no-tts", action="store_true", help="Disable text-to-speech output"
    )
    parser.add_argument(
        "--stt-engine",
        choices=["whisper", "google"],
        help="Speech-to-text engine (overrides config)",
    )
    parser.add_argument(
        "--ai-provider",
        choices=["ollama", "openai"],
        help="AI provider (overrides config)",
    )
    return parser.parse_args()


def main():
    """Application entry point."""
    args = parse_args()

    # Load configuration
    config = load_config(args.config)

    # Apply CLI overrides
    if args.mode:
        config.setdefault("display", {})["mode"] = args.mode
    if args.no_camera:
        config.setdefault("camera", {})["enabled"] = False
    if args.stt_engine:
        config.setdefault("stt", {})["engine"] = args.stt_engine
    if args.ai_provider:
        config.setdefault("ai", {})["provider"] = args.ai_provider

    # Setup logging
    setup_logging(config)

    # Create and start assistant
    assistant = SpeechGuidanceAssistant(config)

    # Handle graceful shutdown on Ctrl+C / SIGTERM
    def signal_handler(sig, frame):
        assistant.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        assistant.start()
        # Keep main thread alive
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        assistant.stop()


if __name__ == "__main__":
    main()
