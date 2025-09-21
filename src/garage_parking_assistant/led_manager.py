# src/garage_parking_assistant/led_manager.py

import time
import logging
from exceptions import LEDManagerError
from led import LED

logger = logging.getLogger(__name__)

class LedManager:
    """
    Manages LED segments based on sensor data and obstacle detection.
    Handles blinking for obstacle indication.
    """

    def __init__(self, config, sensor_manager):
        self.config = config
        self.sensor_manager = sensor_manager
        self.brightness = config.BRIGHTNESS
        self.blinking = False
        self.last_blink_time = 0
        self.blink_state = False
        self.blink_color = (0, 0, 255)  # Blue for blinking

        # Create an instance of the LED class (new approach)
        self.led_strip = LED()
        logger.info("LedManager initialized with a new LED instance.")

    def update_brightness(self, brightness):
        """Update LED brightness."""
        try:
            self.brightness = brightness
            logger.info(f"LED brightness set to {self.brightness}.")
        except Exception as e:
            logger.exception("Failed to update LED brightness.")
            raise LEDManagerError("Failed to update LED brightness") from e

    def start_blinking(self):
        """Initiate LED blinking."""
        try:
            if not self.blinking:
                self.blinking = True
                self.last_blink_time = time.time()
                self.blink_state = False
                logger.info("Started LED blinking.")
            else:
                logger.debug("Blinking already active.")
        except Exception as e:
            logger.exception("Failed to start blinking.")
            raise LEDManagerError("Failed to start blinking") from e

    def stop_blinking(self):
        """Stop LED blinking."""
        try:
            if self.blinking:
                self.blinking = False
                self.clear_leds()
                logger.info("Stopped LED blinking.")
            else:
                logger.debug("Blinking not active.")
        except Exception as e:
            logger.exception("Failed to stop blinking.")
            raise LEDManagerError("Failed to stop blinking") from e

    def is_blinking(self):
        """Check if blinking is active."""
        return self.blinking

    def update_leds(self, distances):
        """
        Update LEDs based on sensor distances or blinking state.
        """
        try:
            if self.blinking:
                current_time = time.time()
                if current_time - self.last_blink_time >= 0.5:
                    self.last_blink_time = current_time
                    self.blink_state = not self.blink_state
                    if self.blink_state:
                        # Turn LEDs on with blink color
                        for segment in ['front', 'left', 'right']:
                            self.led_strip.set_led_segment_color(
                                segment,
                                *self.blink_color,
                                brightness=self.brightness,
                                update_immediately=False
                            )
                        self.led_strip.pixels.show()
                        logger.debug("Blinking: LEDs turned on.")
                    else:
                        # Turn LEDs off
                        self.clear_leds()
                        logger.debug("Blinking: LEDs turned off.")
                return  # Skip normal update while blinking

            # Normal LED update based on distances
            self.update_leds_based_on_distances(distances)
        except Exception as e:
            logger.exception("Failed to update LEDs.")
            raise LEDManagerError("Failed to update LEDs") from e

    def update_leds_based_on_distances(self, distances):
        """Set LED colors based on sensor distance thresholds."""
        try:
            red_threshold = self.sensor_manager.red_distance_threshold
            orange_threshold = self.sensor_manager.orange_distance_threshold

            for sensor in ['front', 'left', 'right']:
                distance = distances.get(sensor)
                if distance is not None:
                    if distance <= red_threshold[sensor]:
                        color = (255, 0, 0)    # Red
                    elif distance <= orange_threshold[sensor]:
                        color = (255, 165, 0) # Orange
                    else:
                        color = (0, 255, 0)  # Green

                    self.led_strip.set_led_segment_color(
                        sensor,
                        *color,
                        brightness=self.brightness,
                        update_immediately=False
                    )
                    logger.debug(f"{sensor.capitalize()} LED set to {color}.")
                else:
                    # Turn off if no distance reading
                    self.led_strip.set_led_segment_color(
                        sensor,
                        0, 0, 0,
                        update_immediately=False
                    )
            self.led_strip.pixels.show()
        except KeyError as e:
            logger.error(f"Invalid sensor name: {e}")
            raise LEDManagerError(f"Invalid sensor name: {e}") from e
        except Exception as e:
            logger.exception("Failed to update LEDs based on distances.")
            raise LEDManagerError("Failed to update LEDs based on distances") from e

    def reset_leds_to_default(self, distances):
        """Reset LEDs to default state based on current distances."""
        try:
            self.update_leds_based_on_distances(distances)
            logger.info("LEDs reset to default state.")
        except Exception as e:
            logger.exception("Failed to reset LEDs to default.")
            raise LEDManagerError("Failed to reset LEDs to default") from e

    def clear_leds(self):
        """Turn off all LEDs."""
        try:
            self.led_strip.clear_leds()
            logger.debug("All LEDs cleared.")
        except Exception as e:
            logger.exception("Failed to clear LEDs.")
