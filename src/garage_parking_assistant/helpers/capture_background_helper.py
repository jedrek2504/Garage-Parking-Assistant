# src/helpers/capture_background_helper.py

import time
import logging
from leds.led import set_led_segment_color, clear_leds
from shared_camera import SharedCamera
import cv2
from exceptions import GarageParkingAssistantError

# Configure logging
logger = logging.getLogger(__name__)

# Constants
GREEN_COLOR = (0, 255, 0)  # Green color in RGB
BRIGHTNESS = 20  # Brightness as 20/255
BACKGROUND_FRAME_PATH = 'background_frame.jpg'

def capture_background_frame(assistant, background_frame_path=BACKGROUND_FRAME_PATH):
    logger.info("Initiating background frame capture process.")

    try:
        # Turn all LED segments to green
        for segment in ['left', 'front', 'right']:
            set_led_segment_color(segment, *GREEN_COLOR, brightness=BRIGHTNESS, update_immediately=True)

        # Allow time for the LEDs to turn on
        logger.info("LED segments turned green with 20/255 brightness. Waiting for 2 seconds before capturing background...")
        time.sleep(2)

        # Capture background frame
        camera = SharedCamera.get_instance()
        frame = camera.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        frame = cv2.flip(frame, -1)
        cv2.imwrite(background_frame_path, frame)
        logger.info(f"Background frame captured and saved as {background_frame_path}.")

        # Keep the LEDs on for additional time if needed
        time.sleep(5)

    except Exception as e:
        logger.exception("Failed to capture background frame.")
        raise GarageParkingAssistantError("Failed to capture background frame.") from e

    finally:
        # Clear all LEDs
        clear_leds()
