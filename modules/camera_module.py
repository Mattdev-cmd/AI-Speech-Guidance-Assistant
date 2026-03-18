"""
Camera module for the Raspberry Pi Camera Rev 1.3.

Captures frames for scene analysis to provide visual context
to the AI response engine.
"""

import io
import logging
import threading
import time

logger = logging.getLogger(__name__)


class CameraModule:
    """Manages the Raspberry Pi Camera Rev 1.3 for scene capture and analysis."""

    def __init__(self, config: dict):
        self.cfg = config.get("camera", {})
        self.enabled = self.cfg.get("enabled", True)
        self.resolution = tuple(self.cfg.get("resolution", [640, 480]))
        self.framerate = self.cfg.get("framerate", 15)
        self.rotation = self.cfg.get("rotation", 0)

        self._camera = None
        self._last_frame = None
        self._lock = threading.Lock()

        if self.enabled:
            self._init_camera()

    def _init_camera(self):
        """Initialize the Pi Camera using picamera2."""
        try:
            from picamera2 import Picamera2

            self._camera = Picamera2()
            cam_config = self._camera.create_still_configuration(
                main={"size": self.resolution}
            )
            self._camera.configure(cam_config)

            if self.rotation:
                from libcamera import Transform

                transform_map = {
                    90: Transform(hflip=False, vflip=False, transpose=True),
                    180: Transform(hflip=True, vflip=True),
                    270: Transform(hflip=True, vflip=True, transpose=True),
                }
                if self.rotation in transform_map:
                    cam_config["transform"] = transform_map[self.rotation]
                    self._camera.configure(cam_config)

            self._camera.start()
            time.sleep(1)  # Warm-up time for auto-exposure
            logger.info(
                "Pi Camera initialized (%dx%d @ %d fps)",
                self.resolution[0],
                self.resolution[1],
                self.framerate,
            )
        except (ImportError, RuntimeError) as e:
            logger.warning("Camera not available: %s", e)
            self.enabled = False

    def capture_frame(self) -> bytes | None:
        """Capture a single JPEG frame from the camera."""
        if not self.enabled or not self._camera:
            return None

        try:
            from PIL import Image

            array = self._camera.capture_array()
            img = Image.fromarray(array)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            frame_data = buf.getvalue()

            with self._lock:
                self._last_frame = frame_data

            logger.debug("Frame captured (%d bytes)", len(frame_data))
            return frame_data
        except Exception as e:
            logger.error("Frame capture failed: %s", e)
            return None

    def get_last_frame(self) -> bytes | None:
        """Return the most recently captured frame."""
        with self._lock:
            return self._last_frame

    def capture_for_analysis(self) -> bytes | None:
        """Capture a lower-resolution frame optimized for AI scene analysis."""
        if not self.enabled or not self._camera:
            return None

        try:
            from PIL import Image

            array = self._camera.capture_array()
            img = Image.fromarray(array)
            # Resize to 320x240 for faster AI processing
            img = img.resize((320, 240))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60)
            return buf.getvalue()
        except Exception as e:
            logger.error("Analysis frame capture failed: %s", e)
            return None

    def cleanup(self):
        """Release camera resources."""
        if self._camera:
            try:
                self._camera.stop()
                self._camera.close()
                logger.info("Camera released")
            except Exception as e:
                logger.warning("Camera cleanup error: %s", e)
