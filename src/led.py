# led.py

import board
import neopixel
import logging

logger = logging.getLogger(__name__)

# LED strip configuration
LED_PIN = board.D18
NUM_LEDS = 60
CONTROL_LEDS = 15
BRIGHTNESS = 0.2
ORDER = neopixel.GRB

pixels = neopixel.NeoPixel(LED_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False, pixel_order=ORDER)

def clear_leds():
    """Turns off all the LEDs."""
    try:
        for i in range(CONTROL_LEDS):
            pixels[i] = (0, 0, 0)
        pixels.show()
        logger.debug("LEDs cleared.")
    except Exception as e:
        logger.exception("Failed to clear LEDs.")

def set_led_color(r, g, b, brightness=255):
    """Set color and brightness for the provided number of LEDs."""
    try:
        adjusted_brightness = brightness / 255  # Normalize brightness to 0.0 - 1.0
        for i in range(CONTROL_LEDS):
            pixels[i] = (
                int(r * adjusted_brightness),
                int(g * adjusted_brightness),
                int(b * adjusted_brightness),
            )
        pixels.show()
        logger.debug(f"Set LEDs to color RGB({r}, {g}, {b}) with brightness {brightness}.")
    except Exception as e:
        logger.exception("Failed to set LED color.")
