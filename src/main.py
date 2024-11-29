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
    level=logging.DEBUG,  # Set to DEBUG to capture detailed logs
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('garage_parking_assistant.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Adjust logging levels for specific modules
logging.getLogger('picamera2.picamera2').setLevel(logging.INFO)

class GarageParkingAssistant:
    def __init__(self):
        self.config = Config()
        self.sensor_manager = SensorManager(self.config)
        self.led_manager = LedManager(self.config, self.sensor_manager)

        self.ai_module = AIModule(self.config, self.on_ai_detection)

        self.system_enabled = self.config.SYSTEM_ENABLED

        self.distances = {'front': None, 'left': None, 'right': None, 'lock': threading.Lock()}

        self.parking_procedure_active = False

        self.garage_door_open = False
        self.user_is_home = False  # New variable

        # Lock to synchronize AI Module state
        self.ai_lock = threading.Lock()

        # Variable to keep track of the current process
        self.process = None  # "parking", "exiting", or None

        # Flag to prevent multiple close commands
        self.close_command_sent = False

        # Initialize MQTT handler with new callbacks
        self.mqtt_handler = MqttHandler(
            config=self.config,
            on_settings_update=self.update_settings,
            on_garage_command=self.on_garage_command,
            on_user_status_update=self.on_user_status_update,
            on_garage_state_update=self.on_garage_state_update
        )

    def update_settings(self, data):
        logger.info(f"Updating settings with data: {data}")
        self.sensor_manager.update_thresholds(data)
        self.led_manager.update_brightness(data.get("brightness", self.led_manager.brightness))
        self.system_enabled = data.get("enabled", self.system_enabled)
        logger.info(f"System enabled set to: {self.system_enabled}")

    def on_garage_command(self, command):
        logger.info(f"Received garage command: {command}")
        if command == "OPEN":
            self.garage_door_open = True
            self.start_parking_procedure()
        elif command == "CLOSE":
            self.garage_door_open = False
            self.stop_parking_procedure()

        self.mqtt_handler.publish_garage_state(self.garage_door_open)
        logger.info(f"Garage door state updated: {'open' if self.garage_door_open else 'closed'}")

    def on_user_status_update(self, status):
        logger.info(f"Received user status update: {status}")
        self.user_is_home = (status.lower() == 'on')
        logger.info(f"User is home: {self.user_is_home}")
        self.update_system_enabled_state()

    def on_garage_state_update(self, state):
        logger.info(f"Received garage door state update: {state}")
        self.garage_door_open = (state.lower() == 'open')
        logger.info(f"Garage door is open: {self.garage_door_open}")
        self.update_system_enabled_state()

    def update_system_enabled_state(self):
        # Enable the system if the user is home and the garage door is open
        previous_state = self.system_enabled
        self.system_enabled = self.user_is_home and self.garage_door_open
        logger.info(f"update_system_enabled_state: user_is_home={self.user_is_home}, garage_door_open={self.garage_door_open}, system_enabled={self.system_enabled}")
        if self.system_enabled != previous_state:
            logger.info(f"System enabled state changed to: {self.system_enabled}")
            # Publish the new system_enabled state
            self.mqtt_handler.publish_system_enabled(self.system_enabled)

    def start_parking_procedure(self):
        with self.ai_lock:
            if not self.parking_procedure_active:
                logger.info("Garage door is open. Starting parking procedure.")

                # Measure distances
                self.sensor_manager.measure_distances(self.distances)

                # Update LEDs based on distances before starting AI detection
                self.led_manager.update_leds(self.distances)

                # Allow time for LEDs to turn on and stabilize
                time.sleep(1)  # Adjust the duration as needed

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

                # Reset the Close Command Flag
                self.close_command_sent = False
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
            # Parking procedure remains active

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

    def handle_garage_closure(self):
        front_distance = self.distances.get('front')
        red_threshold_front = self.sensor_manager.red_distance_threshold.get('front')

        logger.debug(f"handle_garage_closure: front_distance={front_distance}, red_threshold_front={red_threshold_front}")

        if (front_distance is not None and
            front_distance > 0 and  # Ensure distance is positive
            red_threshold_front is not None and
            front_distance <= red_threshold_front and
            self.process == "parking" and
            not self.close_command_sent):

            logger.debug(
                f"Front sensor detected red distance ({front_distance} cm) "
                f"while in 'parking' state. Initiating garage door closure."
            )
            logger.info("Initiating garage door closure.")

            # Send the 'CLOSE' command to the garage door
            self.mqtt_handler.send_garage_command("CLOSE")

            # Update the flag to prevent multiple commands
            self.close_command_sent = True

    def main_loop(self):
        if self.system_enabled:
            if self.led_manager.is_blinking():
                logger.debug("Blinking active. Skipping sensor measurements and MQTT updates.")
                self.led_manager.update_leds(self.distances)
            else:
                self.sensor_manager.measure_distances(self.distances)
                self.led_manager.update_leds(self.distances)
                self.mqtt_handler.publish_distances(self.distances)
                self.mqtt_handler.publish_process(self.process if self.process else "idle")

                # Handle garage door closure automation
                self.handle_garage_closure()

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
            self.start_flask_app()

            logger.info("Starting main loop.")
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
