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

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[logging.FileHandler('garage_parking_assistant.log', mode='w')]
)
logger = logging.getLogger(__name__)

# Adjust logging levels for less verbosity
logging.getLogger('picamera2.picamera2').setLevel(logging.INFO)
logging.getLogger('picamera2').setLevel(logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

class GarageParkingAssistant:
    """
    Core class.
    """
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
            logger.exception("Initialization failed.")
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
            else:
                logger.warning(f"Unknown MQTT topic: {topic}")
        except Exception as e:
            logger.exception(f"Failed to handle MQTT update for topic: {topic}")

    def update_settings(self, payload):
        """
        Update sensor thresholds and LED brightness from MQTT settings.
        """
        try:
            data = json.loads(payload)
            logger.info(f"Updating settings: {data}")
            self.sensor_manager.update_thresholds(data)
            brightness = data.get("brightness", self.led_manager.brightness)
            self.led_manager.update_brightness(brightness)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in settings payload.")
            raise GarageParkingAssistantError("Invalid settings payload.")
        except GarageParkingAssistantError as e:
            logger.error(f"Settings update error: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error updating settings.")
            raise GarageParkingAssistantError("Unexpected settings update error.") from e

    def handle_blinking(self):
        """
        Manage blinking duration and restart AI detection after blinking.
        """
        blink_duration = 10  # seconds
        start_time = time.time()
        while time.time() - start_time < blink_duration:
            if not self.parking_procedure_active:
                return
            time.sleep(1)

        logger.info("Blinking ended. Restarting AI detection.")
        self.led_manager.stop_blinking()
        self.led_manager.reset_leds_to_default(self.distances)
        time.sleep(0.5)
        if self.parking_procedure_active:
            self.ai_module.start()

    def on_ai_detection(self, object_detected):
        """
        Callback for AI detection results.
        """
        try:
            if object_detected:
                logger.info("Obstacle detected. Initiating LED blinking.")
                self.led_manager.start_blinking()
                self.mqtt_handler.publish_ai_detection("DETECTED")
                blink_thread = threading.Thread(target=self.handle_blinking, daemon=True)
                blink_thread.start()
            else:
                logger.info("No obstacle detected.")
                self.mqtt_handler.publish_ai_detection("CLEAR")
        except LEDManagerError as e:
            logger.error(f"LED Manager error: {e}")
            raise
        except Exception as e:
            logger.exception("Error in AI detection callback.")
            raise GarageParkingAssistantError("AI detection callback error.") from e

    def on_garage_command(self, command):
        """
        Handle garage door commands from MQTT.
        """
        try:
            logger.info(f"Received garage command: {command}")
            command = command.upper()
            if command == "OPEN":
                if self.user_is_home:
                    logger.info("User home. Opening garage door.")
                    self.garage_door_open = True
                    self.start_parking_procedure()
                    self.update_system_enabled_state()
                    self.mqtt_handler.publish_garage_state(self.garage_door_open)
                else:
                    logger.warning("Unauthorized attempt to open garage door.")
                    self.mqtt_handler.publish_unauthorized_access_attempt()
            elif command == "CLOSE":
                self.garage_door_open = False
                self.stop_parking_procedure()
                self.update_system_enabled_state()
                self.mqtt_handler.publish_garage_state(self.garage_door_open)
            else:
                logger.warning(f"Unknown garage command: {command}")
                raise GarageParkingAssistantError(f"Unknown garage command: {command}")
        except GarageParkingAssistantError as e:
            logger.error(f"Garage command handling error: {e}")
            raise
        except Exception as e:
            logger.exception("Error handling garage command.")
            raise GarageParkingAssistantError("Garage command handling error.") from e

    def update_system_enabled_state(self):
        """
        Update the system enabled state based on user and garage door status.
        """
        try:
            prev_state = self.system_enabled
            self.system_enabled = self.user_is_home and self.garage_door_open
            logger.info(f"System enabled: {self.system_enabled} (User home: {self.user_is_home}, Garage open: {self.garage_door_open})")
            if self.system_enabled != prev_state:
                self.mqtt_handler.publish_system_enabled(self.system_enabled)
        except Exception as e:
            logger.exception("Failed to update system enabled state.")
            raise GarageParkingAssistantError("System state update failed.") from e

    def on_user_status_update(self, status):
        """
        Update user presence status from MQTT.
        """
        try:
            self.user_is_home = (status.lower() == 'on')
            logger.info(f"User is home: {self.user_is_home}")
            self.update_system_enabled_state()
        except Exception as e:
            logger.exception("Error updating user status.")
            raise GarageParkingAssistantError("User status update error.") from e

    def is_car_in_garage(self):
        """
        Determine if the car is inside based on sensor distances.
        """
        try:
            with self.distances_lock:
                for sensor, distance in self.distances.items():
                    if distance is None or distance > self.sensor_manager.orange_distance_threshold[sensor]:
                        logger.info(f"{sensor.capitalize()} sensor safe: {distance} cm. Car not in garage.")
                        return False
            logger.info("Car detected in garage.")
            return True
        except Exception as e:
            logger.exception("Error determining car presence.")
            raise GarageParkingAssistantError("Car presence determination error.") from e

    def start_parking_procedure(self):
        """
        Initiate parking or exiting procedure based on car position.
        """
        try:
            with self.ai_lock:
                if not self.parking_procedure_active:
                    logger.info("Starting parking procedure.")
                    self.measure_and_update_distances()
                    time.sleep(1)  # Stabilize LEDs

                    if self.is_car_in_garage():
                        self.process = "EXITING"
                        logger.info("Process: EXITING.")
                        self.mqtt_handler.publish_process(self.process)
                    else:
                        self.process = "PARKING"
                        logger.info("Process: PARKING.")
                        self.mqtt_handler.publish_process(self.process)
                        self.ai_module.start()

                    self.parking_procedure_active = True
                else:
                    logger.info("Parking procedure already active.")
        except GarageParkingAssistantError as e:
            logger.error(f"Parking procedure error: {e}")
            raise
        except Exception as e:
            logger.exception("Error starting parking procedure.")
            raise GarageParkingAssistantError("Start parking procedure error.") from e

    def stop_parking_procedure(self):
        """
        Terminate the parking or exiting procedure.
        """
        try:
            with self.ai_lock:
                if self.parking_procedure_active:
                    logger.info("Stopping parking procedure.")
                    self.parking_procedure_active = False
                    self.process = None
                    self.mqtt_handler.publish_process("IDLE")
                    self.ai_module.stop()
                    self.close_command_sent = False
                    self.red_proximity_start_time = None
                    self.mqtt_handler.publish_ai_detection("IDLE")
                else:
                    logger.debug("Parking procedure not active.")
        except Exception as e:
            logger.exception("Error stopping parking procedure.")
            raise GarageParkingAssistantError("Stop parking procedure error.") from e

    def measure_and_update_distances(self):
        """
        Measure sensor distances, update LEDs, and publish via MQTT.
        """
        try:
            with self.distances_lock:
                self.sensor_manager.measure_distances(self.distances)
                self.led_manager.update_leds(self.distances)
                self.mqtt_handler.publish_distances(self.distances)
        except SensorError as e:
            logger.error(f"Sensor measurement error: {e}")
            raise
        except LEDManagerError as e:
            logger.error(f"LED update error: {e}")
            raise
        except MQTTError as e:
            logger.error(f"MQTT publishing error: {e}")
            raise
        except Exception as e:
            logger.exception("Error measuring and updating distances.")
            raise GarageParkingAssistantError("Measure and update distances error.") from e

    def handle_automatic_garage_closure(self):
        """
        Automatically close garage door if car is within red proximity for 5 seconds.
        """
        try:
            with self.distances_lock:
                front_distance = self.distances.get('front')
            red_threshold = self.sensor_manager.red_distance_threshold.get('front')

            logger.debug(f"Front distance: {front_distance} cm, Red threshold: {red_threshold} cm")

            if front_distance and red_threshold:
                if front_distance <= red_threshold:
                    if not self.red_proximity_start_time:
                        self.red_proximity_start_time = time.time()
                        logger.debug("Car entered red proximity. Starting timer.")
                    elif time.time() - self.red_proximity_start_time >= 5:
                        if self.process == "PARKING" and not self.close_command_sent:
                            logger.info("Closing garage door automatically.")
                            self.mqtt_handler.send_garage_command("CLOSE")
                            self.close_command_sent = True
                            self.system_enabled = False
                            self.mqtt_handler.publish_system_enabled(self.system_enabled)
                else:
                    if self.red_proximity_start_time:
                        logger.debug("Car exited red proximity. Resetting timer.")
                    self.red_proximity_start_time = None
            else:
                self.red_proximity_start_time = None
        except MQTTError as e:
            logger.error(f"MQTT error during garage closure: {e}")
            raise
        except Exception as e:
            logger.exception("Error handling automatic garage closure.")
            raise GarageParkingAssistantError("Automatic garage closure error.") from e

    def main_loop(self):
        """
        Main operational loop.
        """
        try:
            if self.system_enabled:
                if self.led_manager.is_blinking():
                    logger.debug("Blinking active. Skipping sensor updates.")
                    self.led_manager.update_leds(self.distances)
                else:
                    self.measure_and_update_distances()
                    self.handle_automatic_garage_closure()
                time.sleep(0.5)
            else:
                with self.distances_lock:
                    self.distances = {'front': None, 'left': None, 'right': None}
                    self.mqtt_handler.publish_distances(self.distances)
                self.stop_parking_procedure()
                self.led_manager.clear_leds()
                logger.info("System disabled.")
                time.sleep(5)
        except (SensorError, LEDManagerError, MQTTError) as e:
            logger.error(f"Operational error: {e}")
        except GarageParkingAssistantError as e:
            logger.critical(f"Critical error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in main loop.")

    def start_flask_app(self):
        """Start the Flask camera streaming app in a separate thread."""
        try:
            flask_thread = threading.Thread(target=run_flask_app, daemon=True)
            flask_thread.start()
            logger.info("Flask app started.")
        except Exception as e:
            logger.exception("Failed to start Flask app.")
            raise GarageParkingAssistantError("Flask app start error.") from e

    def run(self):
        """
        Initialize components and start the main operational loop.
        """
        try:
            self.sensor_manager.setup_sensors()
            self.mqtt_handler.connect()
            self.start_flask_app()
            logger.info("Entering main loop.")
            while True:
                self.main_loop()
        except KeyboardInterrupt:
            logger.info("User interrupted execution.")
        except GarageParkingAssistantError as e:
            logger.critical(f"Application failed: {e}")
        except Exception:
            logger.exception("Unhandled exception in application.")
        finally:
            try:
                self.stop_parking_procedure()
                self.led_manager.clear_leds()
                self.mqtt_handler.disconnect()
                self.sensor_manager.cleanup()
                logger.info("Resources cleaned up.")
            except Exception as e:
                logger.exception("Cleanup failed.")

if __name__ == "__main__":
    try:
        assistant = GarageParkingAssistant()
        assistant.run()
    except GarageParkingAssistantError as e:
        logger.critical(f"Application startup failed: {e}")
    except Exception as e:
        logger.critical("Unhandled exception during startup.", exc_info=True)
