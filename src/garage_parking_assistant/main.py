# src/garage_parking_assistant/main.py

import threading
import logging
import time
import json
from config import Config
from mqtt_handler import MqttHandler
from sensor_manager import SensorManager
from led_manager import LedManager
from obstacle_detection import DetectionModule
from camera_stream import CameraStream
from exceptions import GarageParkingAssistantError, LEDManagerError, MQTTError, SensorError
from state_machine import ParkingStateMachine
from garage_closure import GarageClosureHandler
from metrics import Metrics

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[logging.FileHandler('garage_parking_assistant.log', mode='w')]
)
logger = logging.getLogger(__name__)

# Adjust junk logging
logging.getLogger('picamera2.picamera2').setLevel(logging.INFO)
logging.getLogger('picamera2').setLevel(logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

class GarageParkingAssistant:
    """
    Core class for the Garage-Parking-Assistant.
    """

    def __init__(self):
        try:
            self.config = Config()
            self.sensor_manager = SensorManager(self.config)
            self.led_manager = LedManager(self.config, self.sensor_manager)
            self.ai_module = DetectionModule(self.config, self.on_ai_detection)

            # Initial system state variables
            self.system_enabled = self.config.SYSTEM_ENABLED
            self.garage_door_open = False
            self.user_is_home = False
            self.state_machine = ParkingStateMachine()
            self.close_command_sent = False

            # Holds current sensor distance measurements
            self.distances = {'front': None, 'left': None, 'right': None}

            self.mqtt_handler = MqttHandler(self.config)
            self.garage_closure_handler = GarageClosureHandler()
            self.metrics = Metrics()

            # Locks for thread-safety
            # state_lock: Protects system_enabled, garage_door_open, user_is_home, process states.
            # distances_lock: Protects distance measurements.
            # detection_lock: Protects detection thread start/stop operations.
            self.distances_lock = threading.Lock()
            self.state_lock = threading.Lock()
            self.detection_lock = threading.RLock()

            # Register this assistant as an observer for MQTT messages
            self.mqtt_handler.register_observer(self)
        except Exception as e:
            logger.exception("Initialization failed.")
            raise GarageParkingAssistantError("Initialization failed.") from e

    def update(self, topic, payload):
        """
        Called by MqttHandler when MQTT messages arrive.
        Dispatches to appropriate handlers while ensuring lock usage where needed.
        """
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
        """
        Update sensor thresholds and LED brightness based on incoming MQTT settings.
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
        Manages blinking duration after obstacle detection.
        During blinking, no sensor measurements occur, and sensors are set to None.
        After blinking ends, obstacle detection is restarted if still parking.
        """
        blink_duration = 10
        start_time = time.time()
        while True:
            with self.state_lock:
                if self.state_machine.is_idle():
                    # If parking became idle, stop blinking handling
                    return
            if time.time() - start_time >= blink_duration:
                break
            time.sleep(1)

        # After blink duration ends:
        logger.info("Blinking ended. Restarting obstacle detection.")
        self.led_manager.stop_blinking()

        # Reset LEDs to default state after blinking
        with self.distances_lock:
            self.led_manager.reset_leds_to_default(self.distances)

        # Restart obstacle detection if still parking
        time.sleep(0.5)
        with self.state_lock:
            if self.state_machine.is_parking():
                self.ai_module.start()

    def on_ai_detection(self, object_detected):
        """
        Callback from obstacle module after detection.
        If object detected, start blinking and set distances to None (unavailable).
        """
        try:
            if object_detected:
                logger.info("Obstacle detected. Initiating LED blinking.")
                self.metrics.increment_obstacle()

                # Start blinking
                self.led_manager.start_blinking()

                # During blinking, set all sensor distances to None/unavailable
                with self.distances_lock:
                    for s in self.distances.keys():
                        self.distances[s] = None
                    self.mqtt_handler.publish_distances(self.distances)

                self.mqtt_handler.publish_ai_detection("DETECTED")

                # Handle blinking in a separate thread
                blink_thread = threading.Thread(target=self.handle_blinking, daemon=True)
                blink_thread.start()
            else:
                # No obstacle: publish CLEAR state
                logger.info("No obstacle detected.")
                self.mqtt_handler.publish_ai_detection("CLEAR")
        except LEDManagerError as e:
            logger.error(f"LED Manager error: {e}")
            raise
        except Exception as e:
            logger.exception("Error in obstacle detection callback.")
            raise GarageParkingAssistantError("Obstacle detection callback error.") from e

    def on_garage_command(self, command):
        """
        Handle garage door commands (OPEN/CLOSE).
        Must have state_lock held when calling.
        """
        try:
            logger.info(f"Received garage command: {command}")
            command = command.upper()
            if command == "OPEN":
                if self.user_is_home:
                    logger.info("User home. Opening garage door.")
                    self.garage_door_open = True
                    self.update_system_enabled_state()
                    self.start_parking_procedure()
                    self.mqtt_handler.publish_garage_state(self.garage_door_open)
                else:
                    logger.warning("Unauthorized attempt to open garage door.")
                    self.mqtt_handler.publish_unauthorized_access_attempt()
            elif command == "CLOSE":
                self.garage_door_open = False
                self.update_system_enabled_state()

                self.stop_parking_procedure()
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
        Updates system_enabled based on user presence and garage door state.
        Must have state_lock held.
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
        Updates user_is_home status from MQTT.
        Must have state_lock held.
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
        Check if car is inside based on sensor distances.
        If any sensor is None or distance > orange threshold => car not detected.
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
        Initiate parking or exiting procedure depending on car presence.
        state_lock must be held before calling.
        Acquires ai_lock internally to safely start obstacle detection if needed.
        """
        with self.detection_lock:
            if self.state_machine.is_idle():
                logger.info("Starting parking procedure.")
                self.measure_and_update_distances()
                time.sleep(1)  # Stabilize LEDs after measurement

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
        """
        Stop parking or exiting procedure.
        state_lock must be held before calling.
        Acquires ai_lock to safely stop detection if running.
        """
        with self.detection_lock:
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
        """
        Measure sensor distances and update LEDs and MQTT accordingly.
        Only called when not blinking and system is enabled.
        """
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
        """
        Checks if car proximity persists long enough to trigger automatic closure.
        Must acquire state_lock before calling closure handler.
        """
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
        """
        Main operational loop:
        """
        try:
            with self.state_lock:
                current_enabled = self.system_enabled

            if current_enabled:
                with self.state_lock:
                    blinking = self.led_manager.is_blinking()

                if blinking:
                    logger.debug("Blinking active. Skipping sensor updates.")
                    with self.distances_lock:
                        for s in self.distances.keys():
                            self.distances[s] = None
                        self.mqtt_handler.publish_distances(self.distances)
                        
                    self.led_manager.update_leds(self.distances)

                else:
                    # Normal operation
                    self.measure_and_update_distances()
                    self.handle_automatic_garage_closure()

                # Update metrics periodically
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
                    for s in self.distances:
                        self.distances[s] = None
                    self.mqtt_handler.publish_distances(self.distances)
                time.sleep(5)
        except (SensorError, LEDManagerError, MQTTError) as e:
            logger.error(f"Operational error: {e}")
        except GarageParkingAssistantError as e:
            logger.critical(f"Critical error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in main loop.")

    def start_flask_app(self):
        """
        Starts the Flask camera streaming app in a separate thread.
        """
        try:
            flask_thread = threading.Thread(target=CameraStream.run_flask_app, daemon=True)
            flask_thread.start()
            logger.info("Flask app started.")
        except Exception as e:
            logger.exception("Failed to start Flask app.")
            raise GarageParkingAssistantError("Flask app start error.") from e

    def run(self):
        """
        Entry point after initialization.
        Sets up sensors, connects MQTT, starts Flask app, and enters main_loop.
        On exit, cleans up resources.
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
