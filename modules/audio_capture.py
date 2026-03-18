"""
Audio capture module.

Supports two backends:
  - PyAudio  (preferred, works with ReSpeaker HAT on Raspberry Pi)
  - sounddevice (fallback, works on Windows/macOS/Linux PCs)

Handles microphone input, Voice Activity Detection (VAD),
and produces audio segments ready for speech-to-text processing.
"""

import logging
import struct
import threading
import time
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)

# Try to import backends — at least one must be available
_HAS_PYAUDIO = False
_HAS_SOUNDDEVICE = False
_HAS_WEBRTCVAD = False

try:
    import pyaudio
    _HAS_PYAUDIO = True
except ImportError:
    pass

try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except ImportError:
    pass

try:
    import webrtcvad
    _HAS_WEBRTCVAD = True
except ImportError:
    pass

if not _HAS_PYAUDIO and not _HAS_SOUNDDEVICE:
    raise ImportError("Either 'pyaudio' or 'sounddevice' must be installed for audio capture.")


class AudioCapture:
    """Captures audio from the microphone and detects speech segments."""

    # ReSpeaker 2-Mics Pi HAT identifiers
    RESPEAKER_KEYWORDS = ["seeed", "respeaker", "2mic", "ac108"]

    def __init__(self, config: dict, on_speech_callback=None, on_level_callback=None):
        self.cfg = config.get("audio", {})
        self.sample_rate = self.cfg.get("sample_rate", 16000)
        self.channels = self.cfg.get("channels", 1)
        self.chunk_size = self.cfg.get("chunk_size", 1024)
        self.silence_threshold = self.cfg.get("silence_threshold", 500)
        self.silence_duration = self.cfg.get("silence_duration", 1.5)
        self.max_record_seconds = self.cfg.get("max_record_seconds", 30)
        self.on_speech_callback = on_speech_callback
        self.on_level_callback = on_level_callback

        self._backend = "pyaudio" if _HAS_PYAUDIO else "sounddevice"
        self._pa = None
        self._device_index = None
        self._vad = None
        self._stream = None
        self._running = False
        self._thread = None

        if _HAS_WEBRTCVAD:
            self._vad = webrtcvad.Vad(self.cfg.get("vad_aggressiveness", 2))

        if self._backend == "pyaudio":
            self._pa = pyaudio.PyAudio()
            self._device_index = self._find_respeaker_device()
        else:
            self._device_index = self._find_sd_device()

        logger.info("Audio backend: %s (VAD: %s)", self._backend,
                     "webrtcvad" if _HAS_WEBRTCVAD else "energy-based")

    def _find_respeaker_device(self) -> int:
        """Auto-detect the ReSpeaker 2-Mics Pi HAT audio input device."""
        configured = self.cfg.get("device_index")
        if configured is not None:
            logger.info("Using configured audio device index: %d", configured)
            return configured

        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            name = info.get("name", "").lower()
            if info.get("maxInputChannels", 0) > 0:
                for kw in self.RESPEAKER_KEYWORDS:
                    if kw in name:
                        logger.info("Found ReSpeaker device: '%s' (index %d)", info["name"], i)
                        return i

        # Fallback to default input device
        default = self._pa.get_default_input_device_info()
        logger.warning("ReSpeaker not found, using default: '%s'", default["name"])
        return default["index"]

    def _find_sd_device(self) -> int | None:
        """Find a suitable input device for sounddevice."""
        configured = self.cfg.get("device_index")
        if configured is not None:
            return configured

        default = sd.default.device[0]  # default input device index
        info = sd.query_devices(default)
        logger.info("Using default audio input: '%s' (index %s)", info["name"], default)
        return default

    def _compute_rms(self, audio_data: bytes) -> float:
        """Compute RMS energy of an audio chunk."""
        count = len(audio_data) // 2
        shorts = struct.unpack(f"<{count}h", audio_data)
        sum_sq = sum(s * s for s in shorts)
        return (sum_sq / count) ** 0.5 if count > 0 else 0

    def _is_speech(self, audio_data: bytes) -> bool:
        """Check if audio chunk contains speech using WebRTC VAD or energy."""
        rms = self._compute_rms(audio_data)
        energy_detected = rms > self.silence_threshold

        if self._vad:
            frame_duration_ms = 30
            frame_size = int(self.sample_rate * frame_duration_ms / 1000) * 2
            if len(audio_data) >= frame_size:
                frame = audio_data[:frame_size]
                try:
                    vad_detected = self._vad.is_speech(frame, self.sample_rate)
                    # Use VAD as primary, but fall back to energy if VAD
                    # says no speech yet energy is clearly above threshold.
                    if vad_detected or energy_detected:
                        return True
                    return False
                except Exception:
                    pass

        return energy_detected

    # ---- PyAudio capture loop ----

    def _capture_loop_pyaudio(self):
        """Audio capture loop using PyAudio."""
        logger.info("Audio capture started (pyaudio, device=%d, rate=%d)",
                     self._device_index, self.sample_rate)

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self._device_index,
            frames_per_buffer=self.chunk_size,
        )
        self._read_loop(lambda: self._stream.read(self.chunk_size, exception_on_overflow=False))

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()

    # ---- sounddevice capture loop ----

    def _capture_loop_sd(self):
        """Audio capture loop using sounddevice."""
        logger.info("Audio capture started (sounddevice, device=%s, rate=%d)",
                     self._device_index, self.sample_rate)

        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.chunk_size,
            device=self._device_index,
        )
        self._stream.start()

        def _read():
            data, overflowed = self._stream.read(self.chunk_size)
            return bytes(data)

        self._read_loop(_read)
        self._stream.stop()
        self._stream.close()

    # ---- Shared VAD + segmentation logic ----

    def _read_loop(self, read_fn):
        """Shared loop: reads chunks, detects speech segments, fires callback."""
        speech_buffer = []
        silent_chunks = 0
        is_speaking = False
        chunks_per_second = self.sample_rate / self.chunk_size
        max_chunks = int(self.max_record_seconds * chunks_per_second)
        silence_chunks_threshold = int(self.silence_duration * chunks_per_second)

        while self._running:
            try:
                data = read_fn()
            except OSError as e:
                logger.warning("Audio read error: %s", e)
                continue

            # Emit mic level (RMS) for each chunk
            if self.on_level_callback:
                rms = self._compute_rms(data)
                self.on_level_callback(rms)

            speech_detected = self._is_speech(data)

            if speech_detected and not is_speaking:
                logger.debug("Speech detected (RMS: %.0f, threshold: %d)",
                             self._compute_rms(data), self.silence_threshold)

            if speech_detected:
                if not is_speaking:
                    logger.debug("Speech start detected")
                    is_speaking = True
                    speech_buffer = []
                    silent_chunks = 0
                speech_buffer.append(data)
                silent_chunks = 0
            elif is_speaking:
                speech_buffer.append(data)
                silent_chunks += 1

                if silent_chunks >= silence_chunks_threshold or len(speech_buffer) >= max_chunks:
                    is_speaking = False
                    audio_bytes = b"".join(speech_buffer)
                    speech_buffer = []
                    logger.info(
                        "Speech segment captured: %.1f seconds",
                        len(audio_bytes) / (self.sample_rate * 2),
                    )
                    if self.on_speech_callback:
                        self.on_speech_callback(audio_bytes)

    def start(self):
        """Start audio capture in a background thread."""
        if self._running:
            return
        self._running = True
        target = self._capture_loop_pyaudio if self._backend == "pyaudio" else self._capture_loop_sd
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()
        logger.info("Audio capture thread started")

    def stop(self):
        """Stop audio capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Audio capture stopped")

    def cleanup(self):
        """Release audio resources."""
        self.stop()
        if self._pa:
            self._pa.terminate()
