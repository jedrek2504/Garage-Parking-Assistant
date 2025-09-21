# src/garage_parking_assistant/led.py

import board
import neopixel
import logging
from exceptions import LEDManagerError

logger = logging.getLogger(__name__)

class LED:
    """ The LED class is responsible for initializing and managing the NeoPixel (WS2812B) strip. """
    # LED strip configuration
    LED_PIN = board.D18
    NUM_LEDS = 37  # Total number of LEDs
    BRIGHTNESS = 0.2
    ORDER = neopixel.GRB

    # Define LED segments
    LED_SEGMENTS = {
        'left': {'start': 0, 'end': 11},    # LEDs 0-11
        'front': {'start': 14, 'end': 22},  # LEDs 14-22
        'right': {'start': 25, 'end': 37}   # LEDs 25-37
    }

    def __init__(self):
        """ Initializes the NeoPixel strip. """
        try:
            self.pixels = neopixel.NeoPixel(
                self.LED_PIN,
                self.NUM_LEDS,
                brightness=self.BRIGHTNESS,
                auto_write=False,
                pixel_order=self.ORDER
            )
            logger.info("NeoPixel LED strip initialized successfully.")
        except Exception as e:
            logger.exception("Failed to initialize NeoPixel LED strip.")
            raise LEDManagerError("Failed to initialize NeoPixel LED strip.") from e

    def clear_leds(self):
        """ Turns off all LEDs on the strip. """
        try:
            self.pixels.fill((0, 0, 0))
            self.pixels.show()
            logger.debug("All LEDs turned off.")
        except Exception as e:
            logger.exception("Failed to clear LEDs.")
            raise LEDManagerError("Failed to clear LEDs.") from e

    def set_led_segment_color(self, segment_name, r, g, b, brightness=255, update_immediately=False):
        """ Sets the color and brightness for a specific LED segment. """
        try:
            if segment_name not in self.LED_SEGMENTS:
                logger.error(f"Invalid LED segment name: {segment_name}")
                raise LEDManagerError(f"Invalid LED segment name: {segment_name}")

            adjusted_brightness = brightness / 255  # Normalize brightness to 0.0 - 1.0
            segment = self.LED_SEGMENTS[segment_name]
            for i in range(segment['start'], segment['end']):
                self.pixels[i] = (
                    int(r * adjusted_brightness),
                    int(g * adjusted_brightness),
                    int(b * adjusted_brightness),
                )
            if update_immediately:
                self.pixels.show()
            logger.debug(f"Set {segment_name} LEDs to color RGB({r}, {g}, {b}) with brightness {brightness}.")
        except LEDManagerError:
            raise
        except Exception as e:
            logger.exception(f"Failed to set LED color for {segment_name} segment.")
            raise LEDManagerError(f"Failed to set LED color for {segment_name} segment.") from e
