"""
Text-to-Speech module.

Converts AI-generated guidance and suggestions to spoken audio
output via the ReSpeaker 2-Mics Pi HAT speaker output.
"""

import logging
import tempfile
import threading

logger = logging.getLogger(__name__)


class TextToSpeech:
    """Converts text to spoken audio output."""

    def __init__(self, config: dict):
        self.cfg = config.get("tts", {})
        self.engine_name = self.cfg.get("engine", "pyttsx3")
        self._engine = None
        self._lock = threading.Lock()

        if self.engine_name == "pyttsx3":
            self._init_pyttsx3()

    def _init_pyttsx3(self):
        """Initialize the pyttsx3 offline TTS engine."""
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.cfg.get("rate", 160))
            self._engine.setProperty("volume", self.cfg.get("volume", 0.8))

            # Set voice if specified
            voice_id = self.cfg.get("voice")
            if voice_id:
                self._engine.setProperty("voice", voice_id)

            logger.info("pyttsx3 TTS engine initialized")
        except Exception as e:
            logger.error("Failed to initialize pyttsx3: %s", e)
            self.engine_name = "gtts"

    def speak(self, text: str):
        """Speak the given text aloud.

        Args:
            text: The text to speak.
        """
        if not text.strip():
            return

        with self._lock:
            if self.engine_name == "pyttsx3":
                self._speak_pyttsx3(text)
            else:
                self._speak_gtts(text)

    def _speak_pyttsx3(self, text: str):
        """Speak using pyttsx3 (offline)."""
        try:
            # Stop any previous speech and clear buffer
            self._engine.stop()
            
            # Add new text and speak
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            logger.error("pyttsx3 speak error: %s", e)

    def _speak_gtts(self, text: str):
        """Speak using Google TTS (requires internet)."""
        try:
            from gtts import gTTS
            import os
            import subprocess

            tts = gTTS(text=text, lang="en", slow=False)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tts.save(tmp.name)

            # Play audio using system player
            subprocess.run(
                ["mpg123", "-q", tmp.name],
                check=False,
                timeout=30,
            )
            os.unlink(tmp.name)
        except Exception as e:
            logger.error("gTTS speak error: %s", e)

    def speak_async(self, text: str):
        """Speak text in a background thread."""
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()
        return thread

    def cleanup(self):
        """Release TTS resources."""
        if self._engine and self.engine_name == "pyttsx3":
            try:
                self._engine.stop()
            except Exception:
                pass
