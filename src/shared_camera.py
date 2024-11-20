# shared_camera.py

from picamera2 import Picamera2

class SharedCamera:
    _instance = None

    @staticmethod
    def get_instance():
        if SharedCamera._instance is None:
            SharedCamera._instance = Picamera2()
            video_config = SharedCamera._instance.create_video_configuration(
                main={"size": (640, 480)},
                controls={"FrameDurationLimits": (66666, 66666)},  # ~15 FPS
            )
            SharedCamera._instance.configure(video_config)
            SharedCamera._instance.start()
        return SharedCamera._instance

    @staticmethod
    def stop_instance():
        if SharedCamera._instance is not None:
            SharedCamera._instance.stop()
            SharedCamera._instance = None
