import time
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))  # Points to src/
from garage_parking_assistant.leds.led import set_led_segment_color, clear_leds
from garage_parking_assistant.shared_camera import SharedCamera
import cv2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
GREEN_COLOR = (0, 255, 0)  # Green color in RGB
BRIGHTNESS = 20  # Brightness as 20/255
BACKGROUND_FRAME_PATH = 'background_frame.jpg'

def test_all_segments_green_and_capture_background():
    """
    Turn all LED segments (left, front, right) green with 20/255 brightness,
    then capture and save the background frame.
    """
    try:
        # Set each segment to green
        for segment in ['left', 'front', 'right']:
            set_led_segment_color(segment, *GREEN_COLOR, brightness=BRIGHTNESS, update_immediately=True)

        # Allow time for the LEDs to turn on
        print("LED segments turned green with 20/255 brightness. Waiting for 2 seconds before capturing background...")
        time.sleep(2)

        # Capture background frame
        camera = SharedCamera.get_instance()
        frame = camera.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        frame = cv2.flip(frame, -1)
        cv2.imwrite(BACKGROUND_FRAME_PATH, frame)
        print(f"Background frame captured and saved as {BACKGROUND_FRAME_PATH}.")

        # Keep the LEDs on for additional time if needed
        time.sleep(5)

    finally:
        # Clear all LEDs
        clear_leds()
        print("All LEDs cleared.")

if __name__ == "__main__":
    test_all_segments_green_and_capture_background()
