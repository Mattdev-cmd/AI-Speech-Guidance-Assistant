"""
Speech-to-Text module.

Transcribes audio segments using OpenAI Whisper (local)
or Google Cloud Speech-to-Text (cloud fallback).
"""

import io
import logging
import tempfile
import wave

import numpy as np

logger = logging.getLogger(__name__)


class SpeechToText:
    """Converts audio bytes to text using Whisper or Google STT."""

    def __init__(self, config: dict):
        self.cfg = config.get("stt", {})
        self.engine = self.cfg.get("engine", "whisper")
        self.language = self.cfg.get("language", "en")
        self.sample_rate = config.get("audio", {}).get("sample_rate", 16000)

        self._whisper_model = None
        self._recognizer = None

        if self.engine == "whisper":
            self._init_whisper()
        else:
            self._init_google()

    def _init_whisper(self):
        """Load the Whisper model."""
        try:
            import whisper

            model_name = self.cfg.get("whisper_model", "base")
            logger.info("Loading Whisper model '%s'...", model_name)
            self._whisper_model = whisper.load_model(model_name)
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error("Failed to load Whisper: %s", e)
            logger.info("Falling back to Google STT")
            self.engine = "google"
            self._init_google()

    def _init_google(self):
        """Initialize Google Speech Recognition."""
        try:
            import speech_recognition as sr

            self._recognizer = sr.Recognizer()
            logger.info("Google Speech Recognition initialized")
        except ImportError:
            logger.error("speech_recognition not installed")

    def _audio_bytes_to_wav(self, audio_bytes: bytes) -> str:
        """Write raw PCM audio bytes to a temporary WAV file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_bytes)
        return tmp.name

    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe raw PCM audio bytes to text.

        Args:
            audio_bytes: Raw 16-bit PCM audio data.

        Returns:
            Transcribed text string, or empty string on failure.
        """
        if not audio_bytes:
            return ""

        duration = len(audio_bytes) / (self.sample_rate * 2)
        logger.info("Transcribing %.1f seconds of audio (engine: %s)", duration, self.engine)

        if self.engine == "whisper":
            result = self._transcribe_whisper(audio_bytes)
        else:
            result = self._transcribe_google(audio_bytes)

        if not result:
            logger.warning("STT returned empty transcription – speech may not have been recognized")
        return result

    def _transcribe_whisper(self, audio_bytes: bytes) -> str:
        """Transcribe using local Whisper model."""
        if not self._whisper_model:
            return ""

        try:
            wav_path = self._audio_bytes_to_wav(audio_bytes)
            result = self._whisper_model.transcribe(
                wav_path,
                language=self.language,
                fp16=False,  # Pi 4 doesn't have FP16 GPU
            )
            text = result.get("text", "").strip()
            logger.info("Whisper transcription: '%s'", text[:80])
            return text
        except Exception as e:
            logger.error("Whisper transcription failed: %s", e)
            return ""
        finally:
            import os

            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def _transcribe_google(self, audio_bytes: bytes) -> str:
        """Transcribe using Google Speech Recognition."""
        if not self._recognizer:
            return ""

        try:
            import speech_recognition as sr

            wav_path = self._audio_bytes_to_wav(audio_bytes)
            with sr.AudioFile(wav_path) as source:
                audio = self._recognizer.record(source)

            text = self._recognizer.recognize_google(audio, language=self.language)
            logger.info("Google transcription: '%s'", text[:80])
            return text
        except Exception as e:
            logger.error("Google transcription failed: %s", e)
            return ""
        finally:
            import os

            try:
                os.unlink(wav_path)
            except OSError:
                pass
