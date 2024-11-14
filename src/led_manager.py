import logging
from led import set_led_segment_color, clear_leds

logger = logging.getLogger(__name__)

import threading
import time

class LedManager:
    def __init__(self, config):
        self.brightness = config.BRIGHTNESS
        self.led_blinking = False
        self.led_blink_thread = None
        self.blink_color = (0, 0, 255)  # Blue color
        self.red_distance_threshold = config.RED_DISTANCE_THRESHOLD.copy()
        self.orange_distance_threshold = config.ORANGE_DISTANCE_THRESHOLD.copy()

    def update_brightness(self, brightness):
        self.brightness = brightness

    def is_blinking(self):
        return self.led_blinking

    def start_blinking(self):
        if not self.led_blinking:
            self.led_blinking = True
            self.led_blink_thread = threading.Thread(target=self.led_blink_loop)
            self.led_blink_thread.start()
            logger.info("LED blinking started.")
        else:
            logger.debug("LED blinking already in progress.")

    def stop_blinking(self):
        if self.led_blinking:
            self.led_blinking = False
            if self.led_blink_thread:
                self.led_blink_thread.join()
            # After stopping blinking, update LEDs based on distance
            logger.info("LED blinking stopped.")

    def led_blink_loop(self):
        while self.led_blinking:
            # Blink LEDs on with the blinking color
            set_led_segment_color('front', *self.blink_color, brightness=self.brightness)
            set_led_segment_color('left', *self.blink_color, brightness=self.brightness)
            set_led_segment_color('right', *self.blink_color, brightness=self.brightness)
            time.sleep(0.5)
            # Blink LEDs off
            clear_leds()
            time.sleep(0.5)

    def update_leds_based_on_distance(self, distances):
        with distances['lock']:
            for sensor_name in ['front', 'left', 'right']:
                distance = distances.get(sensor_name)
                if distance is not None:
                    # Determine color based on thresholds
                    if distance < self.red_distance_threshold[sensor_name]:
                        color = (255, 0, 0)  # Red
                    elif distance < self.orange_distance_threshold[sensor_name]:
                        color = (255, 165, 0)  # Orange
                    else:
                        color = (0, 255, 0)  # Green
                    # Set LED segment color
                    set_led_segment_color(sensor_name, *color, brightness=self.brightness)
                    logger.debug(f"{sensor_name.capitalize()} LED segment set to color {color}.")
                else:
                    # Turn off the LED segment if distance is None
                    set_led_segment_color(sensor_name, 0, 0, 0)


    def clear_leds(self):
        clear_leds()
