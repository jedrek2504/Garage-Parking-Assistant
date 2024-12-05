# src/garage_parking_assistant/shared_camera.py

from picamera2 import Picamera2
import threading
import logging

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
                SharedCamera._instance = Picamera2()
                video_config = SharedCamera._instance.create_video_configuration(
                    main={"size": (640, 480)},
                    controls={"FrameDurationLimits": (66666, 66666)},  # ~15 FPS
                )
                SharedCamera._instance.configure(video_config)
                SharedCamera._instance.start()
                logger.info("SharedCamera started.")
            return SharedCamera._instance

    @staticmethod
    def stop_instance():
        """Stop and remove the shared camera instance."""
        with SharedCamera._lock:
            if SharedCamera._instance:
                SharedCamera._instance.stop()
                SharedCamera._instance = None
                logger.info("SharedCamera stopped.")
