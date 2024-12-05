# src/garage_parking_assistant/led_manager.py

import time
import logging
from leds.led import set_led_segment_color, clear_leds, pixels
from exceptions import LEDManagerError

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

    def update_brightness(self, brightness):
        try:
            self.brightness = brightness
            logger.info(f"LED brightness updated to: {self.brightness}")
        except Exception as e:
            logger.exception("Failed to update LED brightness.")
            raise LEDManagerError("Failed to update LED brightness") from e

    def start_blinking(self):
        try:
            if not self.blinking:
                self.blinking = True
                self.last_blink_time = time.time()
                self.blink_state = False
                logger.info("Started blinking.")
            else:
                logger.debug("Blinking already active.")
        except Exception as e:
            logger.exception("Failed to start blinking.")
            raise LEDManagerError("Failed to start blinking") from e

    def stop_blinking(self):
        try:
            if self.blinking:
                self.blinking = False
                self.clear_leds()
                logger.info("Stopped blinking.")
            else:
                logger.debug("Blinking not active.")
        except Exception as e:
            logger.exception("Failed to stop blinking.")
            raise LEDManagerError("Failed to stop blinking") from e

    def is_blinking(self):
        return self.blinking

    def update_leds(self, distances):
        try:
            if self.blinking:
                current_time = time.time()
                if current_time - self.last_blink_time >= 0.5:
                    self.last_blink_time = current_time
                    self.blink_state = not self.blink_state
                    if self.blink_state:
                        # Turn LEDs on
                        for segment in ['front', 'left', 'right']:
                            set_led_segment_color(segment, *self.blink_color, brightness=self.brightness, update_immediately=False)
                        pixels.show()
                        logger.debug("Blinking: LEDs turned on.")
                    else:
                        # Turn LEDs off
                        self.clear_leds()
                        logger.debug("Blinking: LEDs turned off.")
                # When blinking, do not update LEDs based on distance
                return

            # Update LEDs based on sensor measurements
            self.update_leds_based_on_distances(distances)
        except Exception as e:
            logger.exception("Failed to update LEDs.")
            raise LEDManagerError("Failed to update LEDs") from e

    def update_leds_based_on_distances(self, distances):
        try:
            red_thresholds = self.sensor_manager.red_distance_threshold
            orange_thresholds = self.sensor_manager.orange_distance_threshold

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
                    set_led_segment_color(sensor_name, *color, brightness=self.brightness, update_immediately=False)
                    logger.debug(f"{sensor_name.capitalize()} LED segment set to color {color}.")
                else:
                    # Turn off the LED segment if distance is None
                    set_led_segment_color(sensor_name, 0, 0, 0, update_immediately=False)
            pixels.show()
        except KeyError as e:
            logger.error(f"Invalid sensor name when updating LEDs: {e}")
            raise LEDManagerError(f"Invalid sensor name: {e}") from e
        except Exception as e:
            logger.exception("Failed to update LEDs based on distances.")
            raise LEDManagerError("Failed to update LEDs based on distances") from e

    def reset_leds_to_default(self, distances):
        try:
            # Update LEDs based on the current distances
            self.update_leds_based_on_distances(distances)
            logger.info("LEDs reset to default state.")
        except Exception as e:
            logger.exception("Failed to reset LEDs to default state.")
            raise LEDManagerError("Failed to reset LEDs to default state") from e

    def clear_leds(self):
        try:
            clear_leds()
            logger.debug("All LEDs cleared.")
        except Exception as e:
            logger.exception("Failed to clear LEDs.")
            raise LEDManagerError("Failed to clear LEDs") from e
