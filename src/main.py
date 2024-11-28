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

        # New State Variables
        self.system_enabled = False  # System is disabled by default
        self.user_is_home = False  # Track if the user is home

        self.distances = {'front': None, 'left': None, 'right': None, 'lock': threading.Lock()}

        self.parking_procedure_active = False
        self.garage_door_open = False

        # Lock to synchronize AI Module state and system state
        self.ai_lock = threading.Lock()
        self.system_lock = threading.Lock()

        # Variable to keep track of the current process
        self.process = None  # "parking", "exiting", or None

        # Flag to prevent multiple close commands
        self.close_command_sent = False

        # Register event handlers
        self.register_event_handlers()

    def register_event_handlers(self):
        # Subscribe to relevant MQTT topics or Home Assistant events
        self.mqtt_handler.client.message_callback_add("homeassistant/status/user_is_home", self.on_user_status_change)
        self.mqtt_handler.client.message_callback_add(self.config.MQTT_TOPICS["garage_state"], self.on_garage_door_state_change)

    def on_user_status_change(self, client, userdata, msg):
        payload = msg.payload.decode().lower()
        previous_status = self.user_is_home
        self.user_is_home = (payload == 'on')
        logger.info(f"User is home status changed to: {self.user_is_home}")

        # If user becomes home and garage door is open, enable the system
        if self.user_is_home and self.garage_door_open:
            self.enable_system()
        elif not self.user_is_home and self.system_enabled:
            # Optionally handle user leaving home
            pass  # Depending on desired behavior

    def on_garage_door_state_change(self, client, userdata, msg):
        payload = msg.payload.decode().lower()
        previous_state = self.garage_door_open
        self.garage_door_open = (payload == 'open')
        logger.info(f"Garage door state changed to: {self.garage_door_open}")

        if self.garage_door_open and self.user_is_home:
            self.enable_system()
        elif not self.garage_door_open:
            self.disable_system()

    def enable_system(self):
        with self.system_lock:
            if not self.system_enabled:
                logger.info("Enabling Parking System...")
                self.system_enabled = True

                # Turn on LEDs
                self.led_manager.update_brightness(self.config.BRIGHTNESS)
                self.led_manager.update_leds(self.distances)  # Initialize LEDs based on current distances

                # Start distance measurements
                self.sensor_manager.setup_sensors()

                # Allow some delay to ensure LEDs and sensors are active
                time.sleep(1)  # Adjust delay as necessary

                # Confirm LEDs are active and measurements are ongoing
                if self.led_manager.are_leds_active() and self.sensor_manager.are_measurements_active():
                    # Initialize AI Module
                    self.ai_module.start()
                    logger.info("AI Module initialized successfully.")
                else:
                    logger.error("Failed to confirm LEDs or measurements are active. AI Module not initialized.")

                logger.info("Parking System enabled successfully.")
            else:
                logger.debug("Parking System is already enabled.")

    def disable_system(self):
        with self.system_lock:
            if self.system_enabled:
                logger.info("Disabling Parking System...")
                self.system_enabled = False

                # Turn off LEDs
                self.led_manager.clear_leds()

                # Stop distance measurements
                self.sensor_manager.cleanup()

                # Stop AI Module if active
                self.ai_module.stop()

                logger.info("Parking System disabled successfully.")
            else:
                logger.debug("Parking System is already disabled.")

    def update_settings(self, data):
        self.sensor_manager.update_thresholds(data)
        self.led_manager.update_brightness(data.get("brightness", self.led_manager.brightness))
        self.system_enabled = data.get("enabled", self.system_enabled)
        logger.info(f"System enabled set to: {self.system_enabled}")

    def on_garage_command(self, command):
        if command == "OPEN":
            self.garage_door_open = True
            if self.user_is_home:
                self.enable_system()
        elif command == "CLOSE":
            self.garage_door_open = False
            self.disable_system()

        self.mqtt_handler.publish_garage_state(self.garage_door_open)
        logger.info(f"Garage door state updated to: {'open' if self.garage_door_open else 'closed'}")

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

        if (front_distance is not None and
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
            # System is disabled; ensure all components are turned off
            self.led_manager.clear_leds()
            logger.info("System disabled. LEDs turned off.")
            time.sleep(5)

    def run(self):
        try:
            # Initial Setup
            self.mqtt_handler.connect()
            self.start_flask_app()

            # Request initial settings
            self.mqtt_handler.request_settings()

            # Wait for settings to be received
            self.mqtt_handler.wait_for_settings()
            logger.info("Settings received. Parking System is disabled by default.")

            # Main Loop
            while True:
                self.main_loop()
        except KeyboardInterrupt:
            logger.info("Measurement stopped by User.")
        except Exception as e:
            logger.exception("An unexpected error occurred.")
        finally:
            # Ensure system is disabled on exit
            self.disable_system()
            self.led_manager.clear_leds()
            self.mqtt_handler.disconnect()
            self.sensor_manager.cleanup()
            logger.info("Resources cleaned up.")

if __name__ == "__main__":
    assistant = GarageParkingAssistant()
    assistant.run()
