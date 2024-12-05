# src/garage_parking_assistant/leds/led.py

import board
import neopixel
import logging

logger = logging.getLogger(__name__)

# LED configuration
LED_PIN = board.D18
NUM_LEDS = 37
BRIGHTNESS = 0.2
ORDER = neopixel.GRB

# Initialize NeoPixel strip
pixels = neopixel.NeoPixel(LED_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False, pixel_order=ORDER)

# Define LED segments
LED_SEGMENTS = {
    'left': {'start': 0, 'end': 11},    # LEDs 0-10
    'front': {'start': 14, 'end': 22},  # LEDs 14-21
    'right': {'start': 25, 'end': 37}   # LEDs 25-36
}

def clear_leds():
    """Turn off all LEDs."""
    try:
        pixels.fill((0, 0, 0))
        pixels.show()
        logger.debug("All LEDs turned off.")
    except Exception as e:
        logger.exception("Failed to clear LEDs.")

def set_led_segment_color(segment_name, r, g, b, brightness=255, update_immediately=False):
    """
    Set color and brightness for a specific LED segment.
    """
    try:
        adjusted_brightness = brightness / 255
        segment = LED_SEGMENTS[segment_name]
        for i in range(segment['start'], segment['end']):
            pixels[i] = (
                int(r * adjusted_brightness),
                int(g * adjusted_brightness),
                int(b * adjusted_brightness),
            )
        if update_immediately:
            pixels.show()
        logger.debug(f"{segment_name.capitalize()} LEDs set to RGB({r}, {g}, {b}) with brightness {brightness}.")
    except Exception as e:
        logger.exception(f"Failed to set color for {segment_name} LEDs.")
