# main.py

import time
import threading
import logging
from config import Config
from mqtt_handler import MqttHandler
from sensor import UltrasonicSensor, setup_sensors, cleanup
from led import set_led_segment_color, clear_leds
from camera_stream import run_flask_app

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('garage_parking_assistant.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

class GarageParkingAssistant:
    def __init__(self):
        self.config = Config()
        self.mqtt_handler = MqttHandler(
            config=self.config,
            on_settings_update=self.update_settings
        )
        self.red_distance_threshold = self.config.RED_DISTANCE_THRESHOLD.copy()
        self.orange_distance_threshold = self.config.ORANGE_DISTANCE_THRESHOLD.copy()
        self.brightness = self.config.BRIGHTNESS
        self.system_enabled = self.config.SYSTEM_ENABLED

        # Initialize sensors
        self.sensors = {
            'front': UltrasonicSensor(trig_pin=22, echo_pin=23, name='Front Sensor'),
            'left': UltrasonicSensor(trig_pin=24, echo_pin=25, name='Left Sensor'),
            'right': UltrasonicSensor(trig_pin=17, echo_pin=27, name='Right Sensor')
        }

    def update_settings(self, data):
        for sensor in ['front', 'left', 'right']:
            self.red_distance_threshold[sensor] = data.get(f"red_distance_threshold_{sensor}", self.red_distance_threshold[sensor])
            self.orange_distance_threshold[sensor] = data.get(f"orange_distance_threshold_{sensor}", self.orange_distance_threshold[sensor])
        self.brightness = data.get("brightness", self.brightness)
        self.system_enabled = data.get("enabled", self.system_enabled)

    def start_flask_app(self):
        flask_thread = threading.Thread(target=run_flask_app)
        flask_thread.daemon = True
        flask_thread.start()
        logger.info("Flask app started in a separate thread.")

    def run(self):
        try:
            setup_sensors(self.sensors)
            logger.info("Sensors setup complete.")

            self.mqtt_handler.connect()
            self.mqtt_handler.request_settings()
            self.start_flask_app()

            self.mqtt_handler.wait_for_settings()
            logger.info("Settings received. Starting main loop.")

            while True:
                if self.system_enabled:
                    distances = {}
                    for sensor_name, sensor in self.sensors.items():
                        distance = sensor.measure_distance()
                        if distance is not None:
                            distances[sensor_name] = distance
                            logger.debug(f"{sensor_name.capitalize()} measured distance: {distance} cm")

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
                            logger.error(f"Failed to measure distance for {sensor_name}.")
                            # Optionally turn off the LED segment
                            set_led_segment_color(sensor_name, 0, 0, 0)

                        time.sleep(0.05)  # Short delay to prevent sensor interference

                    # Publish distances via MQTT
                    self.mqtt_handler.publish_distances(distances)
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
            cleanup()
            logger.info("Resources cleaned up.")

if __name__ == "__main__":
    assistant = GarageParkingAssistant()
    assistant.run()
