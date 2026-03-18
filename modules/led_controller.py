"""
ReSpeaker 2-Mics Pi HAT v2.0 LED controller.

Controls the 3x APA102 RGB LEDs on the HAT via SPI
to provide visual feedback for the assistant state.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# APA102 LED protocol constants
_LED_START = 0x00
_LED_END = 0xFF
_NUM_LEDS = 3  # ReSpeaker 2-Mics Pi HAT has 3 APA102 LEDs


class LEDController:
    """Controls the APA102 LEDs on the ReSpeaker 2-Mics Pi HAT v2.0."""

    def __init__(self, config: dict):
        self.cfg = config.get("leds", {})
        self.enabled = self.cfg.get("enabled", True)
        self.brightness = min(max(self.cfg.get("brightness", 20), 0), 31)

        self.colors = {
            "listening": self.cfg.get("listening_color", [0, 0, 255]),
            "processing": self.cfg.get("processing_color", [255, 165, 0]),
            "ready": self.cfg.get("ready_color", [0, 255, 0]),
            "error": self.cfg.get("error_color", [255, 0, 0]),
            "off": [0, 0, 0],
        }

        self._spi = None
        self._animation_thread = None
        self._animating = False

        if self.enabled:
            self._init_spi()

    def _init_spi(self):
        """Initialize SPI bus for APA102 LED communication."""
        try:
            import spidev

            self._spi = spidev.SpiDev()
            self._spi.open(0, 1)  # ReSpeaker uses SPI bus 0, device 1
            self._spi.max_speed_hz = 8000000
            self._spi.mode = 0
            logger.info("SPI initialized for LED control")
        except (ImportError, OSError) as e:
            logger.warning("SPI not available, LEDs disabled: %s", e)
            self.enabled = False

    def _build_frame(self, colors: list[list[int]]) -> list[int]:
        """Build an APA102 SPI data frame for the given LED colors."""
        # Start frame: 4 bytes of 0x00
        frame = [0x00] * 4

        for r, g, b in colors:
            # LED frame: 111 + 5-bit brightness + BGR
            frame.append(0xE0 | self.brightness)
            frame.append(b & 0xFF)
            frame.append(g & 0xFF)
            frame.append(r & 0xFF)

        # End frame
        frame.extend([0xFF] * 4)
        return frame

    def _write_leds(self, colors: list[list[int]]):
        """Write colors to all LEDs."""
        if not self.enabled or not self._spi:
            return

        # Pad or truncate to exactly _NUM_LEDS
        while len(colors) < _NUM_LEDS:
            colors.append([0, 0, 0])
        colors = colors[:_NUM_LEDS]

        frame = self._build_frame(colors)
        try:
            self._spi.writebytes(frame)
        except OSError as e:
            logger.error("LED write error: %s", e)

    def set_state(self, state: str):
        """Set all LEDs to a predefined state color."""
        self._stop_animation()
        color = self.colors.get(state, self.colors["off"])
        self._write_leds([color] * _NUM_LEDS)
        logger.debug("LEDs set to state: %s", state)

    def set_color(self, r: int, g: int, b: int):
        """Set all LEDs to a custom RGB color."""
        self._stop_animation()
        self._write_leds([[r, g, b]] * _NUM_LEDS)

    def _breathing_loop(self, color: list[int]):
        """Animate a breathing effect."""
        step = 0
        while self._animating:
            # Sine-wave brightness modulation
            import math

            factor = (math.sin(step * 0.1) + 1) / 2
            r = int(color[0] * factor)
            g = int(color[1] * factor)
            b = int(color[2] * factor)
            self._write_leds([[r, g, b]] * _NUM_LEDS)
            step += 1
            time.sleep(0.05)

    def breathe(self, state: str):
        """Start a breathing animation for the given state."""
        self._stop_animation()
        color = self.colors.get(state, self.colors["processing"])
        self._animating = True
        self._animation_thread = threading.Thread(
            target=self._breathing_loop, args=(color,), daemon=True
        )
        self._animation_thread.start()

    def _stop_animation(self):
        """Stop any running LED animation."""
        self._animating = False
        if self._animation_thread:
            self._animation_thread.join(timeout=1)
            self._animation_thread = None

    def off(self):
        """Turn off all LEDs."""
        self.set_state("off")

    def cleanup(self):
        """Release SPI resources."""
        self._stop_animation()
        self.off()
        if self._spi:
            self._spi.close()
            logger.info("SPI closed")
