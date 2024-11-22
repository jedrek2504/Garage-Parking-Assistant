# src/shared_camera.py

from picamera2 import Picamera2
import threading
import logging

logger = logging.getLogger(__name__)

class SharedCamera:
    _instance = None
    _lock = threading.Lock()

    @staticmethod
    def get_instance():
        with SharedCamera._lock:
            if SharedCamera._instance is None:
                SharedCamera._instance = Picamera2()
                video_config = SharedCamera._instance.create_video_configuration(
                    main={"size": (640, 480)},
                    controls={"FrameDurationLimits": (66666, 66666)},  # ~15 FPS
                )
                SharedCamera._instance.configure(video_config)
                SharedCamera._instance.start()
                logger.info("SharedCamera instance created and started.")
            return SharedCamera._instance

    @staticmethod
    def stop_instance():
        with SharedCamera._lock:
            if SharedCamera._instance is not None:
                SharedCamera._instance.stop()
                SharedCamera._instance = None
                logger.info("SharedCamera instance stopped.")
