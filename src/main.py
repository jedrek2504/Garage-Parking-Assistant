# main.py

import time
import threading
import logging
from config import Config
from mqtt_handler import MqttHandler
from sensor_manager import SensorManager
from led_manager import LedManager
from ai_module import AIModule
from camera_stream import run_flask_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('garage_parking_assistant.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

class GarageParkingAssistant:
    def __init__(self):
        self.config = Config()
        self.sensor_manager = SensorManager(self.config)
        self.led_manager = LedManager(self.config, self.sensor_manager)  # Pass sensor_manager
        self.mqtt_handler = MqttHandler(
            config=self.config,
            on_settings_update=self.update_settings,
            on_garage_command=self.on_garage_command
        )
        self.ai_module = AIModule(self.config, self.on_ai_detection)

        self.system_enabled = self.config.SYSTEM_ENABLED

        # Shared distances with a lock
        self.distances = {'front': None, 'left': None, 'right': None, 'lock': threading.Lock()}

        # Parking procedure state
        self.parking_procedure_active = False

        # Garage door state
        self.garage_door_open = False

    def update_settings(self, data):
        self.sensor_manager.update_thresholds(data)
        self.led_manager.update_brightness(data.get("brightness", self.led_manager.brightness))
        self.system_enabled = data.get("enabled", self.system_enabled)
        logger.info(f"System enabled set to: {self.system_enabled}")

    def on_garage_command(self, command):
        if command == "OPEN":
            self.garage_door_open = True
            self.start_parking_procedure()
        elif command == "CLOSE":
            self.garage_door_open = False
            self.stop_parking_procedure()

        # Publish the state back to Home Assistant
        self.mqtt_handler.publish_garage_state(self.garage_door_open)
        logger.info(f"Garage door state updated to: {'OPEN' if self.garage_door_open else 'CLOSED'}")

    def on_ai_detection(self, object_detected):
        if object_detected:
            logger.info("Object detected by AI analysis. Starting LED blinking.")
            self.led_manager.start_blinking()
        else:
            logger.info("No object detected by AI analysis. Stopping LED blinking.")
            self.led_manager.stop_blinking()

    def start_flask_app(self):
        flask_thread = threading.Thread(target=run_flask_app, args=(self.distances,))
        flask_thread.daemon = True
        flask_thread.start()
        logger.info("Flask app started in a separate thread.")

    def start_parking_procedure(self):
        if not self.parking_procedure_active:
            logger.info("Garage door is open. Starting parking procedure.")
            self.parking_procedure_active = True
            self.ai_module.start()
        else:
            logger.debug("Parking procedure already active.")

    def stop_parking_procedure(self):
        if self.parking_procedure_active:
            logger.info("Garage door is closed or conditions not met. Stopping parking procedure.")
            self.parking_procedure_active = False
            self.ai_module.stop()
            self.led_manager.stop_blinking()
            self.led_manager.clear_leds()
        else:
            logger.debug("Parking procedure not active.")

    def main_loop(self):
        if self.system_enabled:
            if self.led_manager.is_blinking():
                # Skip sensor measurements and MQTT updates during blinking
                logger.debug("Blinking active. Skipping sensor measurements and MQTT updates.")
                self.led_manager.update_leds(self.distances)
            else:
                self.sensor_manager.measure_distances(self.distances)
                self.led_manager.update_leds(self.distances)
                self.mqtt_handler.publish_distances(self.distances)
            time.sleep(0.5)  # Adjust sleep time as necessary
        else:
            self.stop_parking_procedure()
            self.led_manager.clear_leds()
            logger.info("System disabled. LEDs turned off.")
            time.sleep(5)

    def run(self):
        try:
            self.sensor_manager.setup_sensors()

            self.mqtt_handler.connect()
            self.mqtt_handler.request_settings()
            self.start_flask_app()

            self.mqtt_handler.wait_for_settings()
            logger.info("Settings received. Starting main loop.")

            while True:
                self.main_loop()
        except KeyboardInterrupt:
            logger.info("Measurement stopped by User.")
        except Exception as e:
            logger.exception("An unexpected error occurred.")
        finally:
            self.stop_parking_procedure()
            self.led_manager.clear_leds()
            self.mqtt_handler.disconnect()
            self.sensor_manager.cleanup()
            logger.info("Resources cleaned up.")

if __name__ == "__main__":
    assistant = GarageParkingAssistant()
    assistant.run()
