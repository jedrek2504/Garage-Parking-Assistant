import time
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from led import set_led_segment_color, clear_leds

# Constants
GREEN_COLOR = (0, 255, 0)  # Green color in RGB
BRIGHTNESS = 20  # Brightness as 20/255

def test_all_segments_green():
    """
    Turn all LED segments (left, front, right) green with 20/255 brightness.
    """
    try:
        # Set each segment to green
        for segment in ['left', 'front', 'right']:
            set_led_segment_color(segment, *GREEN_COLOR, brightness=BRIGHTNESS, update_immediately=True)

        # Keep the LEDs on for 5 seconds
        print("LED segments turned green with 20/255 brightness. Waiting for 5 seconds...")
        time.sleep(10)

    finally:
        # Clear all LEDs
        clear_leds()
        print("All LEDs cleared.")

if __name__ == "__main__":
    test_all_segments_green()
