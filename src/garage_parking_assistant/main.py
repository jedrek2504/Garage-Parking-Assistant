# src/garage_parking_assistant/main.py

import threading
import logging
import time
import json
from config import Config
from mqtt_handler import MqttHandler
from sensor_manager import SensorManager
from led_manager import LedManager
from ai_detection import AIModule
from camera_stream import run_flask_app
from exceptions import GarageParkingAssistantError, LEDManagerError, MQTTError, SensorError
from ..helpers.capture_background_helper import capture_background_frame

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('garage_parking_assistant.log', mode='w'),
        logging.StreamHandler()  # Optionally log to console as well
    ]
)
logger = logging.getLogger(__name__)

# Adjust logging for picamera2
logging.getLogger('picamera2.picamera2').setLevel(logging.INFO)
logging.getLogger('picamera2').setLevel(logging.INFO)


class GarageParkingAssistant:
    def __init__(self):
        try:
            self.config = Config()
            self.sensor_manager = SensorManager(self.config)
            self.led_manager = LedManager(self.config, self.sensor_manager)
            self.ai_module = AIModule(self.config, self.on_ai_detection)
            self.system_enabled = self.config.SYSTEM_ENABLED
            self.distances = {'front': None, 'left': None, 'right': None}
            self.distances_lock = threading.Lock()
            self.parking_procedure_active = False
            self.garage_door_open = False
            self.user_is_home = False
            self.process = None  # "PARKING", "EXITING", or None
            self.close_command_sent = False
            self.mqtt_handler = MqttHandler(self.config)
            self.mqtt_handler.register_observer(self)
            self.ai_lock = threading.RLock()
            self.red_proximity_start_time = None
        except Exception as e:
            logger.exception("Failed to initialize GarageParkingAssistant.")
            raise GarageParkingAssistantError("Initialization failed.") from e

    def update(self, topic, payload):
        """
        Observer method called by MqttHandler when a message is received.
        """
        try:
            if topic == self.config.MQTT_TOPICS["settings"]:
                self.update_settings(payload)
            elif topic == self.config.MQTT_TOPICS["garage_command"]:
                self.on_garage_command(payload)
            elif topic == self.config.MQTT_TOPICS["user_status"]:
                self.on_user_status_update(payload)
            elif topic == self.config.MQTT_TOPICS["garage_state"]:
                self.on_garage_state_update(payload)
            else:
                logger.warning(f"Unknown topic received: {topic}")
        except Exception as e:
            logger.exception(f"Failed to handle update for topic: {topic}")

    def update_settings(self, payload):
        try:
            data = json.loads(payload)
            logger.info(f"Updating settings with data: {data}")
            self.sensor_manager.update_thresholds(data)
            brightness = data.get("brightness", self.led_manager.brightness)
            self.led_manager.update_brightness(brightness)
        except json.JSONDecodeError:
            logger.error("Failed to decode settings payload")
            raise GarageParkingAssistantError("Failed to decode settings payload")
        except GarageParkingAssistantError as e:
            logger.error(f"Error updating settings: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error while updating settings.")
            raise GarageParkingAssistantError("Unexpected error while updating settings") from e

    def handle_blinking(self):
        blink_duration = 10  # Blinking set to 10s
        start_time = time.time()
        while time.time() - start_time < blink_duration:
            if not self.parking_procedure_active:
                return
            time.sleep(1)

        logger.info("Blinking period ended. AI Module will re-analyze the scene.")
        self.led_manager.stop_blinking()
        self.led_manager.reset_leds_to_default(self.distances)
        time.sleep(0.5)
        if self.parking_procedure_active:
            self.ai_module.start()

    def on_ai_detection(self, object_detected):
        try:
            if object_detected:
                logger.info("AI detected an obstacle. Initiating LED blinking.")
                self.led_manager.start_blinking()
                self.mqtt_handler.publish_ai_detection("DETECTED")
                blink_thread = threading.Thread(target=self.handle_blinking, daemon=True)
                blink_thread.start()
            else:
                logger.info("AI detected no obstacle.")
                self.mqtt_handler.publish_ai_detection("CLEAR")
        except LEDManagerError as e:
            logger.error(f"LED Manager error during AI detection handling: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error in AI detection callback.")
            raise GarageParkingAssistantError("Unexpected error in AI detection callback") from e

    def on_garage_command(self, command):
        try:
            logger.info(f"Received garage command: {command}")
            command = command.upper()
            if command == "OPEN":
                if self.user_is_home:
                    logger.info("User is home. Proceeding to open the garage door.")
                    self.garage_door_open = True
                    self.start_parking_procedure()
                    self.update_system_enabled_state()
                    self.mqtt_handler.publish_garage_state(self.garage_door_open)
                    logger.info(f"Garage door state updated: {'open' if self.garage_door_open else 'closed'}")
                else:
                    logger.warning("Attempt to open garage door denied. User is not home.")
                    self.mqtt_handler.publish_unauthorized_access_attempt()
            elif command == "CLOSE":
                self.garage_door_open = False
                self.stop_parking_procedure()
                self.update_system_enabled_state()
                self.mqtt_handler.publish_garage_state(self.garage_door_open)
                logger.info(f"Garage door state updated: {'open' if self.garage_door_open else 'closed'}")
            else:
                logger.warning(f"Unknown garage command received: {command}")
                raise GarageParkingAssistantError(f"Unknown garage command received: {command}")
        except GarageParkingAssistantError as e:
            logger.error(f"Error handling garage command: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error while handling garage command.")
            raise GarageParkingAssistantError("Unexpected error while handling garage command") from e

    def update_system_enabled_state(self):
        try:
            previous_state = self.system_enabled
            self.system_enabled = self.user_is_home and self.garage_door_open
            logger.info(
                f"update_system_enabled_state: user_is_home={self.user_is_home}, garage_door_open={self.garage_door_open}, system_enabled={self.system_enabled}"
            )
            if self.system_enabled != previous_state:
                logger.info(f"System enabled state changed to: {self.system_enabled}")
                self.mqtt_handler.publish_system_enabled(self.system_enabled)
        except Exception as e:
            logger.exception("Failed to update system enabled state.")
            raise GarageParkingAssistantError("Failed to update system enabled state") from e

    def on_user_status_update(self, status):
        try:
            self.user_is_home = (status.lower() == 'on')
            logger.info(f"Received user status update: {status}. User is home: {self.user_is_home}")
            self.update_system_enabled_state()
        except Exception as e:
            logger.exception("Failed to handle user status update.")
            raise GarageParkingAssistantError("Failed to handle user status update") from e

    def on_garage_state_update(self, state):
        try:
            logger.info(f"Received garage door state update: {state}")
            self.garage_door_open = (state.lower() == 'open')
            logger.info(f"Garage door is open: {self.garage_door_open}")
            self.update_system_enabled_state()
        except Exception as e:
            logger.exception("Failed to handle garage door state update.")
            raise GarageParkingAssistantError("Failed to handle garage door state update") from e

    def is_car_in_garage(self):
        """
        Determines if a car is present in the garage based on sensor distances.

        Returns:
            bool: True if a car is detected, False otherwise.
        """
        try:
            with self.distances_lock:
                for sensor_name in ['front', 'left', 'right']:
                    distance = self.distances.get(sensor_name)
                    if distance is None:
                        logger.warning(f"{sensor_name} sensor reading is None. Assuming safe distance.")
                        return False
                    orange_threshold = self.sensor_manager.orange_distance_threshold[sensor_name]
                    if distance > orange_threshold:
                        logger.info(f"{sensor_name} sensor indicates safe distance: {distance} cm")
                        return False
            logger.info("All sensors detect close distance. Car is in garage")
            return True
        except Exception as e:
            logger.exception("Failed to determine if car is in garage.")
            raise GarageParkingAssistantError("Failed to determine if car is in garage") from e

    def start_parking_procedure(self):
        try:
            with self.ai_lock:
                if not self.parking_procedure_active:
                    logger.info("Garage door is open. Starting parking procedure.")
                    self.measure_and_update_distances()

                    # Allow time for LEDs to turn on and stabilize
                    time.sleep(1)

                    car_in_garage = self.is_car_in_garage()

                    if car_in_garage:
                        self.process = "EXITING"
                        logger.info("Process identified: Exiting the garage.")
                        self.mqtt_handler.publish_process(self.process)
                    else:
                        self.process = "PARKING"
                        logger.info("Process identified: Parking procedure.")
                        self.mqtt_handler.publish_process(self.process)
                        self.ai_module.start()

                    self.parking_procedure_active = True
                else:
                    logger.info("Parking procedure already active.")
        except GarageParkingAssistantError as e:
            logger.error(f"Error starting parking procedure: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error while starting parking procedure.")
            raise GarageParkingAssistantError("Unexpected error while starting parking procedure") from e

    def stop_parking_procedure(self):
        try:
            with self.ai_lock:
                if self.parking_procedure_active:
                    logger.info("Garage door is closed. Stopping parking procedure.")
                    self.parking_procedure_active = False
                    self.process = None
                    self.mqtt_handler.publish_process("IDLE")
                    self.ai_module.stop()
                    self.close_command_sent = False
                    self.red_proximity_start_time = None
                    self.mqtt_handler.publish_ai_detection("IDLE")
                else:
                    logger.info("Parking procedure not active.")
        except Exception as e:
            logger.exception("Failed to stop parking procedure.")
            raise GarageParkingAssistantError("Failed to stop parking procedure") from e

    def measure_and_update_distances(self):
        try:
            with self.distances_lock:
                self.sensor_manager.measure_distances(self.distances)
                self.led_manager.update_leds(self.distances)
                self.mqtt_handler.publish_distances(self.distances)
        except SensorError as e:
            logger.error(f"Sensor error during distance measurement: {e}")
            raise
        except LEDManagerError as e:
            logger.error(f"LED Manager error during distance update: {e}")
            raise
        except MQTTError as e:
            logger.error(f"MQTT error during distance publishing: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error during measure_and_update_distances.")
            raise GarageParkingAssistantError("Unexpected error during measure_and_update_distances") from e

    def handle_automatic_garage_closure(self):
        try:
            with self.distances_lock:
                front_distance = self.distances.get('front')
            red_threshold_front = self.sensor_manager.red_distance_threshold.get('front')

            logger.debug(
                f"handle_garage_closure: front_distance={front_distance}, red_threshold_front={red_threshold_front}"
            )

            if (front_distance is not None and
                    front_distance > 0 and
                    red_threshold_front is not None):

                if front_distance <= red_threshold_front:
                    # Car is within red proximity
                    if self.red_proximity_start_time is None:
                        # Record the time when the car first enters red proximity
                        self.red_proximity_start_time = time.time()
                        logger.debug("Car entered red proximity, starting timer.")
                    else:
                        # Check if the car has been within red proximity for 5 seconds
                        elapsed_time = time.time() - self.red_proximity_start_time
                        logger.debug(f"Car has been within red proximity for {elapsed_time:.2f} seconds.")
                        if (elapsed_time >= 5 and
                                self.process == "PARKING" and
                                not self.close_command_sent):
                            logger.debug(
                                f"Front sensor detected red distance ({front_distance} cm) "
                                f"for {elapsed_time:.2f} seconds while in 'PARKING' state. Initiating garage door closure."
                            )
                            logger.info("Initiating garage door closure.")

                            self.mqtt_handler.send_garage_command("CLOSE")
                            self.close_command_sent = True

                            # Disable the system after closure
                            self.system_enabled = False
                            self.mqtt_handler.publish_system_enabled(self.system_enabled)
                            logger.info("System disabled after garage door closure.")
                else:
                    # Car is not within red proximity, reset the timer
                    if self.red_proximity_start_time is not None:
                        logger.debug("Car exited red proximity, resetting timer.")
                    self.red_proximity_start_time = None
            else:
                # Front distance is invalid, reset the timer
                self.red_proximity_start_time = None
        except MQTTError as e:
            logger.error(f"MQTT error during automatic garage closure: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error during handle_automatic_garage_closure.")
            raise GarageParkingAssistantError("Unexpected error during handle_automatic_garage_closure") from e

    def main_loop(self):
        try:
            if self.system_enabled:
                # System is enabled
                if self.led_manager.is_blinking():
                    logger.debug("Blinking active. Skipping sensor measurements and MQTT updates.")
                    self.led_manager.update_leds(self.distances)
                else:
                    self.measure_and_update_distances()
                    self.handle_automatic_garage_closure()

                time.sleep(0.5)
            else:
                # System is disabled
                with self.distances_lock:
                    # Set all distances to None
                    self.distances = {'front': None, 'left': None, 'right': None}
                    self.mqtt_handler.publish_distances(self.distances)
                self.stop_parking_procedure()
                self.led_manager.clear_leds()
                logger.info("System disabled.")
                time.sleep(5)
        except (SensorError, LEDManagerError, MQTTError) as e:
            logger.error(f"Operational error in main loop: {e}")
            # Depending on the severity, decide whether to continue or terminate
        except GarageParkingAssistantError as e:
            logger.critical(f"Critical error in main loop: {e}")
            # Decide on recovery or shutdown
        except Exception as e:
            logger.exception("Unexpected error in main loop.")

    def start_flask_app(self):
        try:
            flask_thread = threading.Thread(target=run_flask_app, daemon=True)
            flask_thread.start()
            logger.info("Flask app started in a separate thread.")
        except Exception as e:
            logger.exception("Failed to start Flask app.")
            raise GarageParkingAssistantError("Failed to start Flask app") from e

    def run(self):
        try:
            self.sensor_manager.setup_sensors()
            self.mqtt_handler.connect()
            self.start_flask_app()

            self.capture_and_set_background_frame()

            logger.info("Starting main loop.")
            while True:
                self.main_loop()
        except KeyboardInterrupt:
            logger.info("Measurement stopped by User.")
        except GarageParkingAssistantError as e:
            logger.critical(f"Application failed due to critical error: {e}")
        except Exception:
            logger.exception("An unexpected error occurred in the main execution.")
        finally:
            try:
                self.stop_parking_procedure()
                self.led_manager.clear_leds()
                self.mqtt_handler.disconnect()
                self.sensor_manager.cleanup()
                logger.info("Resources cleaned up.")
            except Exception as e:
                logger.exception("Failed during cleanup.")


if __name__ == "__main__":
    try:
        assistant = GarageParkingAssistant()
        assistant.run()
    except GarageParkingAssistantError as e:
        logger.critical(f"Application failed to start: {e}")
    except Exception as e:
        logger.critical("Unhandled exception during application startup.", exc_info=True)
