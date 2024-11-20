# capture_background.py

import time
import cv2
from picamera2 import Picamera2
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('capture_background.log', mode='w'),
        logging.StreamHandler()  # Log to console
    ]
)
logger = logging.getLogger(__name__)

def capture_background_image(output_filename='background_frame.jpg'):
    try:
        picam2 = Picamera2()
        # Configure the camera to capture a still image
        video_config = picam2.create_video_configuration(
            main={"size": (640, 480)},
            controls={"FrameDurationLimits": (66666, 66666)}  # ~15 FPS
        )
        picam2.configure(video_config)
        picam2.start()
        logger.info("Camera started and configured for capturing background image.")

        time.sleep(2)  # Allow camera to warm up

        # Capture the image
        frame_rgb = picam2.capture_array()  # RGB format
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)  # Convert to BGR
        frame_bgr = cv2.flip(frame_bgr, -1)  # Flip vertically and horizontally

        # Save the background frame
        cv2.imwrite(output_filename, frame_bgr)
        logger.info(f"Background image captured and saved as {output_filename}.")

    except Exception as e:
        logger.exception("Failed to capture background image.")
    finally:
        picam2.stop()
        logger.info("Camera stopped.")

if __name__ == "__main__":
    capture_background_image()
