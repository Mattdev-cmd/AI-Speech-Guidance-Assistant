#!/usr/bin/env python3
"""
Live Web UI — Run the Speech Guidance Assistant on any PC.

Uses your PC microphone to listen, transcribes speech, sends it
to an AI backend (Ollama or OpenAI), and shows real-time STREAMING response
suggestions in a Gemini-like web dashboard. No Raspberry Pi hardware needed.

Usage:
    python demo_web.py                        # Ollama (local)
    python demo_web.py --ai openai            # OpenAI
    python demo_web.py --stt google           # Google STT instead of Whisper
    python demo_web.py --no-tts               # Disable spoken guidance

    Then open http://localhost:5000 in your browser.
"""

import argparse
import logging
import os
import signal
import socket
import sys
import threading
import time

import yaml

from modules.audio_capture import AudioCapture
from modules.speech_to_text import SpeechToText
from modules.ai_engine import AIResponseEngine
from modules.streaming_response import StreamingResponseHandler
from modules.text_to_speech import TextToSpeech
from modules.display import WebDisplay

logger = logging.getLogger("demo_web")


class LiveWebAssistant:
    """Runs the full speech pipeline with a Gemini-like streaming web dashboard — no Pi hardware."""

    def __init__(self, config: dict):
        self.config = config
        self._running = False
        self._processing_lock = threading.Lock()

        logger.info("Initializing modules...")
        self.display = WebDisplay(config)
        self.stt = SpeechToText(config)
        self.ai = AIResponseEngine(config)
        self.streaming = StreamingResponseHandler(config)  # NEW: Streaming handler
        self.tts = TextToSpeech(config) if not config.get("_no_tts") else None
        self.audio = AudioCapture(
            config,
            on_speech_callback=self._on_speech,
            on_level_callback=self._on_mic_level
        )
        logger.info("All modules initialized")

    def _on_mic_level(self, rms: float):
        """Callback for live mic level (RMS) updates."""
        self.display.show_mic_level(rms)

    def _on_speech(self, audio_bytes: bytes):
        """Callback when a speech segment is detected."""
        if not self._processing_lock.acquire(blocking=False):
            logger.debug("Already processing, skipping segment")
            return
        try:
            self._process(audio_bytes)
        finally:
            self._processing_lock.release()

    def _process(self, audio_bytes: bytes):
        """Pipeline: STT -> AI (streaming) -> Display -> optional TTS."""
        self.display.show_processing()

        try:
            transcript = self.stt.transcribe(audio_bytes)
            if not transcript:
                logger.info("No speech transcribed, back to listening")
                return

            self.display.show_transcript_text(transcript)

            # Build messages for streaming
            messages = [
                {"role": "system", "content": self.ai.system_prompt},
                {"role": "user", "content": transcript}
            ]

            # Start streaming response
            self.display.stream_response_start("AI Response")

            # Collect response while streaming
            full_response = ""

            def on_token(token: str):
                nonlocal full_response
                full_response += token
                self.display.stream_token(token)  # Emit token to web UI

            def on_complete(response: str):
                self.display.stream_response_end()

            def on_error(error: str):
                logger.error("Streaming error: %s", error)
                self.display.show_error(error)

            # Stream the response
            self.streaming.stream_response(
                messages,
                on_token=on_token,
                on_complete=on_complete,
                on_error=on_error
            )

            # If TTS is enabled, speak the response
            if full_response and self.tts and self.display.tts_enabled:
                self.tts.speak_async(full_response)

        except Exception as e:
            logger.error("Processing pipeline error: %s", e)
            self.display.show_error(str(e))
        finally:
            self.display.show_listening()

    def start(self):
        self._running = True
        self.display.start()

        # Wait for the web server to be ready
        time.sleep(1)

        self.audio.start()
        self.display.show_listening()
        logger.info("Assistant started and listening")

    def stop(self):
        self._running = False
        self.audio.cleanup()
        if self.tts:
            self.tts.cleanup()
        logger.info("Assistant stopped")


def load_config(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Live Speech Guidance Assistant — PC Web UI"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--port", type=int, default=5000, help="Web UI port (default: 5000)"
    )
    parser.add_argument(
        "--stt",
        choices=["whisper", "google"],
        help="Speech-to-text engine (default: from config)",
    )
    parser.add_argument(
        "--ai",
        choices=["ollama", "openai"],
        help="AI provider (default: from config)",
    )
    parser.add_argument(
        "--no-tts", action="store_true", help="Disable spoken guidance output"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)

    # Force web display, disable camera & LEDs
    config.setdefault("display", {}).update({"mode": "web", "web_port": args.port})
    config.setdefault("camera", {})["enabled"] = False
    config.setdefault("leds", {})["enabled"] = False

    if args.stt:
        config.setdefault("stt", {})["engine"] = args.stt
    if args.ai:
        config.setdefault("ai", {})["provider"] = args.ai
    if args.no_tts:
        config["_no_tts"] = True

    # Basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    stt_engine = config.get("stt", {}).get("engine", "whisper")
    ai_provider = config.get("ai", {}).get("provider", "ollama")

    print("\n" + "=" * 55)
    print("  Speech Guidance Assistant — Live Web UI")
    print("=" * 55)
    print(f"  STT Engine : {stt_engine}")
    print(f"  AI Provider: {ai_provider}")
    print(f"  TTS        : {'disabled' if args.no_tts else 'enabled'}")
    print("=" * 55)

    assistant = LiveWebAssistant(config)
    assistant.start()

    # Verify web server is up
    try:
        with socket.create_connection(("127.0.0.1", args.port), timeout=2):
            pass
    except OSError:
        print(f"\n  ERROR: Could not start server on port {args.port}.")
        print("  Try closing other apps using that port, or use --port <number>.")
        return

    print(f"\n  Open http://localhost:{args.port} in your browser")
    print("  Speak into your microphone — results appear in real time")
    print("  Press Ctrl+C to stop\n")

    def signal_handler(sig, frame):
        assistant.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        assistant.stop()


if __name__ == "__main__":
    main()
