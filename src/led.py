# led.py

import board
import neopixel
import logging

logger = logging.getLogger(__name__)

# LED strip configuration
LED_PIN = board.D18
NUM_LEDS = 30  # Total number of LEDs
BRIGHTNESS = 0.2
ORDER = neopixel.GRB

# Initialize the NeoPixel strip
pixels = neopixel.NeoPixel(LED_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False, pixel_order=ORDER)

# Define LED segments
LED_SEGMENTS = {
    'left': {'start': 0, 'end': 10},    # LEDs 0-9
    'front': {'start': 10, 'end': 20},  # LEDs 10-19
    'right': {'start': 20, 'end': 30}   # LEDs 20-29
}

def clear_leds():
    """Turns off all the LEDs."""
    try:
        pixels.fill((0, 0, 0))
        pixels.show()
        logger.debug("All LEDs cleared.")
    except Exception as e:
        logger.exception("Failed to clear LEDs.")

def set_led_segment_color(segment_name, r, g, b, brightness=255):
    """Set color and brightness for a specific LED segment."""
    try:
        adjusted_brightness = brightness / 255  # Normalize brightness to 0.0 - 1.0
        segment = LED_SEGMENTS[segment_name]
        for i in range(segment['start'], segment['end']):
            pixels[i] = (
                int(r * adjusted_brightness),
                int(g * adjusted_brightness),
                int(b * adjusted_brightness),
            )
        pixels.show()
        logger.debug(f"Set {segment_name} LEDs to color RGB({r}, {g}, {b}) with brightness {brightness}.")
    except Exception as e:
        logger.exception(f"Failed to set LED color for {segment_name} segment.")
