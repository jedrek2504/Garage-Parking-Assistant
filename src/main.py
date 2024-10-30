# main.py

import time
import threading
import json
import logging
from config import Config
from mqtt_handler import MqttHandler
from sensor import setup_sensor, measure_distance
from led import set_led_color, clear_leds
from camera_stream import run_flask_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('garage_parking_assistant.log')
    ]
)
logger = logging.getLogger(__name__)

class GarageParkingAssistant:
    def __init__(self):
        self.config = Config()
        self.mqtt_handler = MqttHandler(
            config=self.config,
            on_settings_update=self.update_settings,
            on_led_set=self.set_led_color
        )
        self.red_distance_threshold = self.config.RED_DISTANCE_THRESHOLD
        self.orange_distance_threshold = self.config.ORANGE_DISTANCE_THRESHOLD
        self.brightness = self.config.BRIGHTNESS
        self.system_enabled = self.config.SYSTEM_ENABLED

    def update_settings(self, data):
        self.red_distance_threshold = data.get("red_distance_threshold", self.red_distance_threshold)
        self.orange_distance_threshold = data.get("orange_distance_threshold", self.orange_distance_threshold)
        self.brightness = data.get("brightness", self.brightness)
        self.system_enabled = data.get("enabled", self.system_enabled)

    def set_led_color(self, data):
        if data.get("state") == "ON":
            color = data.get("color", {})
            r = color.get("r", 0)
            g = color.get("g", 0)
            b = color.get("b", 0)
            set_led_color(r, g, b, self.brightness)
            logger.info(f"LED color set to RGB({r}, {g}, {b}) with brightness {self.brightness}.")
        else:
            clear_leds()
            logger.info("LEDs cleared.")

    def start_flask_app(self):
        flask_thread = threading.Thread(target=run_flask_app)
        flask_thread.daemon = True
        flask_thread.start()
        logger.info("Flask app started in a separate thread.")

    def run(self):
        try:
            setup_sensor()
            logger.info("Sensor setup complete.")

            self.mqtt_handler.connect()
            self.mqtt_handler.request_settings()
            self.start_flask_app()

            self.mqtt_handler.wait_for_settings()
            logger.info("Settings received. Starting main loop.")

            while True:
                if self.system_enabled:
                    distance = measure_distance()
                    if distance is not None:
                        logger.debug(f"Measured Distance: {distance} cm")

                        if distance < self.red_distance_threshold:
                            set_led_color(255, 0, 0, self.brightness)
                            logger.debug("Set LED color to RED.")
                        elif distance < self.orange_distance_threshold:
                            set_led_color(255, 165, 0, self.brightness)
                            logger.debug("Set LED color to ORANGE.")
                        else:
                            set_led_color(0, 255, 0, self.brightness)
                            logger.debug("Set LED color to GREEN.")

                        self.mqtt_handler.publish_distance(distance)
                    else:
                        logger.error("Failed to measure distance.")
                else:
                    clear_leds()
                    logger.info("System disabled. LEDs turned off.")
                    time.sleep(5)

                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Measurement stopped by User.")
        except Exception as e:
            logger.exception("An unexpected error occurred.")
        finally:
            clear_leds()
            self.mqtt_handler.disconnect()
            logger.info("Resources cleaned up.")

if __name__ == "__main__":
    assistant = GarageParkingAssistant()
    assistant.run()
