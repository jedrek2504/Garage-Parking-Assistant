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
from state_machine import ParkingStateMachine
from garage_closure import GarageClosureHandler
from metrics import Metrics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[logging.FileHandler('garage_parking_assistant.log', mode='w')]
)
logger = logging.getLogger(__name__)

# Adjust less-important logging
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
            self.garage_door_open = False
            self.user_is_home = False

            self.state_machine = ParkingStateMachine()
            self.close_command_sent = False

            self.distances = {'front': None, 'left': None, 'right': None}
            self.mqtt_handler = MqttHandler(self.config)
            self.garage_closure_handler = GarageClosureHandler()
            self.metrics = Metrics()

            # Locks
            self.distances_lock = threading.Lock()
            self.state_lock = threading.Lock()
            self.ai_lock = threading.RLock()

        except Exception as e:
            logger.exception("Initialization failed.")
            raise GarageParkingAssistantError("Initialization failed.") from e

    def update(self, topic, payload):
        try:
            if topic == self.config.MQTT_TOPICS["settings"]:
                self.update_settings(payload)
            elif topic == self.config.MQTT_TOPICS["garage_command"]:
                with self.state_lock:
                    self.on_garage_command(payload)
            elif topic == self.config.MQTT_TOPICS["user_status"]:
                with self.state_lock:
                    self.on_user_status_update(payload)
            else:
                logger.warning(f"Unknown MQTT topic: {topic}")
        except Exception as e:
            logger.exception(f"Failed to handle MQTT update for topic: {topic}")

    def update_settings(self, payload):
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
        blink_duration = 10
        start_time = time.time()
        while True:
            with self.state_lock:
                # If parking procedure stopped, end blinking
                if self.state_machine.is_idle():
                    return
            if time.time() - start_time >= blink_duration:
                break
            time.sleep(1)

        logger.info("Blinking ended. Restarting AI detection.")
        self.led_manager.stop_blinking()
        with self.distances_lock:
            self.led_manager.reset_leds_to_default(self.distances)

        time.sleep(0.5)
        with self.state_lock:
            if self.state_machine.is_parking():
                self.ai_module.start()

    def on_ai_detection(self, object_detected):
        try:
            if object_detected:
                logger.info("Obstacle detected. Initiating LED blinking.")
                self.metrics.increment_obstacle()
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
        try:
            self.user_is_home = (status.lower() == 'on')
            logger.info(f"User is home: {self.user_is_home}")
            self.update_system_enabled_state()
        except Exception as e:
            logger.exception("Error updating user status.")
            raise GarageParkingAssistantError("User status update error.") from e

    def is_car_in_garage(self):
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
        with self.ai_lock:
            if self.state_machine.is_idle():
                logger.info("Starting parking procedure.")
                self.measure_and_update_distances()
                time.sleep(1)  # Stabilize LEDs

                if self.is_car_in_garage():
                    self.state_machine.start_exiting()
                else:
                    self.state_machine.start_parking()

                self.mqtt_handler.publish_process(self.state_machine.process)

                if self.state_machine.is_parking():
                    self.ai_module.start()

            else:
                logger.info("Parking procedure already active.")

    def stop_parking_procedure(self):
        with self.ai_lock:
            if not self.state_machine.is_idle():
                logger.info("Stopping parking procedure.")
                self.state_machine.set_idle()
                self.mqtt_handler.publish_process(None)
                self.ai_module.stop()
                self.close_command_sent = False
                self.mqtt_handler.publish_ai_detection("IDLE")
            else:
                logger.debug("Parking procedure not active.")

    def measure_and_update_distances(self):
        try:
            with self.distances_lock:
                self.sensor_manager.measure_distances(self.distances)
                self.led_manager.update_leds(self.distances)
                self.mqtt_handler.publish_distances(self.distances)
        except SensorError as e:
            logger.error(f"Sensor measurement error: {e}")
        except LEDManagerError as e:
            logger.error(f"LED update error: {e}")
        except MQTTError as e:
            logger.error(f"MQTT publishing error: {e}")
        except Exception as e:
            logger.exception("Error measuring and updating distances.")
            raise GarageParkingAssistantError("Measure and update distances error.") from e

    def handle_automatic_garage_closure(self):
        with self.distances_lock:
            front_distance = self.distances.get('front')
        red_threshold = self.sensor_manager.red_distance_threshold.get('front')

        with self.state_lock:
            self.close_command_sent, self.system_enabled = self.garage_closure_handler.handle_automatic_garage_closure(
                front_distance,
                red_threshold,
                self.state_machine.process,
                self.close_command_sent,
                self.system_enabled,
                self.mqtt_handler.send_garage_command,
                self.mqtt_handler.publish_system_enabled
            )

    def main_loop(self):
        try:
            with self.state_lock:
                current_enabled = self.system_enabled

            if current_enabled:
                # System enabled
                with self.state_lock:
                    blinking = self.led_manager.is_blinking()

                if blinking:
                    logger.debug("Blinking active. Skipping sensor updates.")
                    with self.distances_lock:
                        self.led_manager.update_leds(self.distances)
                else:
                    self.measure_and_update_distances()
                    self.handle_automatic_garage_closure()

                self.metrics.increment_cycle()
                self.metrics.log_metrics_if_due()
                time.sleep(0.5)
            else:
                # System disabled
                with self.state_lock:
                    self.stop_parking_procedure()
                self.led_manager.clear_leds()
                logger.info("System disabled.")
                with self.distances_lock:
                    self.distances = {'front': None, 'left': None, 'right': None}
                    self.mqtt_handler.publish_distances(self.distances)
                time.sleep(5)
        except (SensorError, LEDManagerError, MQTTError) as e:
            logger.error(f"Operational error: {e}")
        except GarageParkingAssistantError as e:
            logger.critical(f"Critical error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in main loop.")

    def start_flask_app(self):
        try:
            flask_thread = threading.Thread(target=run_flask_app, daemon=True)
            flask_thread.start()
            logger.info("Flask app started.")
        except Exception as e:
            logger.exception("Failed to start Flask app.")
            raise GarageParkingAssistantError("Flask app start error.") from e

    def run(self):
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
                with self.state_lock:
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
