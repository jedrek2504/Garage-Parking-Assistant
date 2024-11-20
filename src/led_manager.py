# src/led_manager.py

import time
import threading
import logging
from led import set_led_segment_color, clear_leds

logger = logging.getLogger(__name__)

class LedManager:
    def __init__(self, config, sensor_manager):
        self.config = config
        self.sensor_manager = sensor_manager
        self.brightness = config.BRIGHTNESS
        self.blinking = False
        self.last_blink_time = 0
        self.blink_state = False
        self.blink_color = (0, 0, 255)  # Blue for blinking indication
        self.default_state = {}

    def update_brightness(self, brightness):
        self.brightness = brightness
        logger.info(f"LED brightness updated to: {self.brightness}")

    def start_blinking(self):
        if not self.blinking:
            self.blinking = True
            self.last_blink_time = time.time()
            self.blink_state = False
            logger.info("Started blinking.")
        else:
            logger.debug("Blinking already active.")

    def stop_blinking(self):
        if self.blinking:
            self.blinking = False
            self.clear_leds()
            logger.info("Stopped blinking.")
        else:
            logger.debug("Blinking not active.")

    def is_blinking(self):
        return self.blinking

    def update_leds(self, distances):
        if self.blinking:
            current_time = time.time()
            if current_time - self.last_blink_time >= 0.5:
                self.last_blink_time = current_time
                self.blink_state = not self.blink_state
                if self.blink_state:
                    # Turn LEDs on
                    set_led_segment_color('front', *self.blink_color, brightness=self.brightness)
                    set_led_segment_color('left', *self.blink_color, brightness=self.brightness)
                    set_led_segment_color('right', *self.blink_color, brightness=self.brightness)
                    logger.debug("Blinking: LEDs turned on.")
                else:
                    # Turn LEDs off
                    self.clear_leds()
                    logger.debug("Blinking: LEDs turned off.")
            # When blinking, do not update LEDs based on distance
            return

        # Handle LEDs based on distance thresholds
        red_thresholds = self.sensor_manager.red_distance_threshold
        orange_thresholds = self.sensor_manager.orange_distance_threshold

        with distances['lock']:
            for sensor_name in ['front', 'left', 'right']:
                distance = distances.get(sensor_name)
                if distance is not None:
                    # Determine color based on thresholds
                    if distance <= red_thresholds[sensor_name]:
                        color = (255, 0, 0)  # Red
                    elif distance <= orange_thresholds[sensor_name]:
                        color = (255, 165, 0)  # Orange
                    else:
                        color = (0, 255, 0)  # Green
                    # Set LED segment color
                    set_led_segment_color(sensor_name, *color, brightness=self.brightness)
                    logger.debug(f"{sensor_name.capitalize()} LED segment set to color {color}.")
                else:
                    # Turn off the LED segment if distance is None
                    set_led_segment_color(sensor_name, 0, 0, 0)

    def reset_leds_to_default(self):
        # Optionally, set LEDs to a default state after blinking
        # For example, turn them off or set to a specific color
        self.clear_leds()
        logger.info("LEDs reset to default state.")

    def clear_leds(self):
        clear_leds()
        logger.debug("All LEDs cleared.")
