# src/garage_parking_assistant/shared_camera.py

from picamera2 import Picamera2
import threading
import logging
from exceptions import CameraError

logger = logging.getLogger(__name__)

class SharedCamera:
    """
    Singleton class to manage shared camera instance.
    Ensures only one camera instance is active.
    """
    _instance = None
    _lock = threading.Lock()

    @staticmethod
    def get_instance():
        """Get or create the shared camera instance."""
        with SharedCamera._lock:
            if SharedCamera._instance is None:
                try:
                    SharedCamera._instance = Picamera2()
                    video_config = SharedCamera._instance.create_video_configuration(
                        main={"size": (640, 480)},
                        controls={"FrameDurationLimits": (66666, 66666)},  # ~15 FPS
                    )
                    SharedCamera._instance.configure(video_config)
                    SharedCamera._instance.start()
                    logger.info("SharedCamera instance created and started.")
                except Exception as e:
                    logger.exception("Failed to initialize SharedCamera.")
                    raise CameraError("SharedCamera", "Failed to initialize camera.") from e
            return SharedCamera._instance

    @staticmethod
    def stop_instance():
        """Stop and remove the shared camera instance."""
        with SharedCamera._lock:
            if SharedCamera._instance is not None:
                try:
                    SharedCamera._instance.stop()
                    logger.info("SharedCamera instance stopped.")
                except Exception as e:
                    logger.exception("Failed to stop SharedCamera.")
                    raise CameraError("SharedCamera", "Failed to stop camera.") from e
                finally:
                    SharedCamera._instance = None
