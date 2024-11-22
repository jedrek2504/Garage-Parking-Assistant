# src/main.py

import time
import threading
import logging
from config import Config
from mqtt_handler import MqttHandler
from sensor_manager import SensorManager
from led_manager import LedManager
from ai_detection import AIModule
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
        self.led_manager = LedManager(self.config, self.sensor_manager)
        self.mqtt_handler = MqttHandler(
            config=self.config,
            on_settings_update=self.update_settings,
            on_garage_command=self.on_garage_command
        )
        self.ai_module = AIModule(self.config, self.on_ai_detection)

        self.system_enabled = self.config.SYSTEM_ENABLED

        self.distances = {'front': None, 'left': None, 'right': None, 'lock': threading.Lock()}

        self.parking_procedure_active = False

        self.garage_door_open = False

        # Lock to synchronize AI Module state
        self.ai_lock = threading.Lock()

        # Variable to keep track of the current process
        self.process = None  # "parking", "exiting", or None

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

        self.mqtt_handler.publish_garage_state(self.garage_door_open)
        logger.info(f"Garage door state updated to: {'OPEN' if self.garage_door_open else 'CLOSED'}")

    def start_parking_procedure(self):
        with self.ai_lock:
            if not self.parking_procedure_active:
                logger.info("Garage door is open. Starting parking procedure.")

                # Determine the process based on sensor readings
                self.sensor_manager.measure_distances(self.distances)

                # Check sensor readings to determine if the car is present
                close_object_detected = self.is_close_object_detected()

                if close_object_detected:
                    self.process = "exiting"
                    logger.info("Process identified: Exiting the garage.")
                    # Publish process to MQTT
                    self.mqtt_handler.publish_process(self.process)
                    # Do not start the AI module
                else:
                    self.process = "parking"
                    logger.info("Process identified: Parking procedure.")
                    # Publish process to MQTT
                    self.mqtt_handler.publish_process(self.process)
                    # Start AI detection to check for obstacles
                    self.ai_module.start()

                self.parking_procedure_active = True
            else:
                logger.debug("Parking procedure already active.")

    def is_close_object_detected(self):
        with self.distances['lock']:
            for sensor_name in ['front', 'left', 'right']:
                distance = self.distances.get(sensor_name)
                if distance is None:
                    logger.warning(f"{sensor_name} sensor reading is None. Assuming object not close.")
                    return False  # If any sensor reading is None, we cannot proceed
                orange_threshold = self.sensor_manager.orange_distance_threshold[sensor_name]
                if distance > orange_threshold:
                    logger.info(f"{sensor_name} sensor indicates safe distance: {distance} cm")
                    return False  # If any sensor is not within danger distance, return False
            # If we get here, all sensors have distance <= orange_threshold
            logger.info("All sensors detect close objects.")
            return True


    def stop_parking_procedure(self):
        with self.ai_lock:
            if self.parking_procedure_active:
                logger.info("Garage door is closed. Stopping parking procedure.")
                self.parking_procedure_active = False
                self.process = None  # Reset the process state
                self.mqtt_handler.publish_process("idle")  # Publish idle state

                self.ai_module.stop()
                self.led_manager.stop_blinking()
                self.led_manager.clear_leds()
            else:
                logger.debug("Parking procedure not active.")

    def on_ai_detection(self, object_detected):
        if object_detected:
            logger.info("AI detected an obstacle. Initiating LED blinking.")
            self.led_manager.start_blinking()

            # Publish AI detection event
            self.mqtt_handler.publish_ai_detection(True)

            # Start a timer for the blinking duration (10 seconds)
            blink_thread = threading.Thread(target=self.handle_blinking_duration, daemon=True)
            blink_thread.start()
        else:
            logger.info("AI detected no obstacle.")
            # Publish AI detection event
            self.mqtt_handler.publish_ai_detection(False)

    def handle_blinking_duration(self):
        # Blink LEDs for 10 seconds
        blink_duration = 10
        start_time = time.time()
        while time.time() - start_time < blink_duration:
            if not self.parking_procedure_active:
                return  # Exit if parking procedure is stopped
            time.sleep(1)

        # After blinking period, allow AI Module to re-analyze
        logger.info("Blinking period ended. AI Module will re-analyze the scene.")
        self.led_manager.stop_blinking()
        # Update LEDs based on distances
        self.led_manager.reset_leds_to_default(self.distances)
        # Wait a short delay to ensure LEDs have updated
        time.sleep(0.5)  # Adjust if necessary
        # Restart the AI module to analyze again
        if self.parking_procedure_active:
            self.ai_module.start()

    def start_flask_app(self):
        flask_thread = threading.Thread(target=run_flask_app, args=(self.distances,))
        flask_thread.daemon = True
        flask_thread.start()
        logger.info("Flask app started in a separate thread.")

    def main_loop(self):
        if self.system_enabled:
            if self.led_manager.is_blinking():
                logger.debug("Blinking active. Skipping sensor measurements and MQTT updates.")
                self.led_manager.update_leds(self.distances)
            else:
                self.sensor_manager.measure_distances(self.distances)
                self.led_manager.update_leds(self.distances)
                self.mqtt_handler.publish_distances(self.distances)
            time.sleep(0.5)
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
