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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('garage_parking_assistant.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Adjust logging for picamera2
logging.getLogger('picamera2.picamera2').setLevel(logging.INFO)
logging.getLogger('picamera2').setLevel(logging.INFO)

class GarageParkingAssistant:
    def __init__(self):
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
        self.process = None  # "parking", "exiting", or None
        self.close_command_sent = False
        self.mqtt_handler = MqttHandler(self.config)
        self.mqtt_handler.register_observer(self)
        self.ai_lock = threading.RLock()
        self.red_proximity_start_time = None

    def update(self, topic, payload):
        """
        Observer method called by MqttHandler when a message is received.
        """
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

    def update_settings(self, payload):
        try:
            data = json.loads(payload)
            logger.info(f"Updating settings with data: {data}")
            self.sensor_manager.update_thresholds(data)
            brightness = data.get("brightness", self.led_manager.brightness)
            self.led_manager.update_brightness(brightness)
            self.system_enabled = data.get("enabled", self.system_enabled)
            logger.info(f"System enabled set to: {self.system_enabled}")
        except json.JSONDecodeError:
            logger.error("Failed to decode settings payload")

    def handle_blinking(self):
        blink_duration = 10 # Blinking set to 10s
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
        if object_detected:
            logger.info("AI detected an obstacle. Initiating LED blinking.")
            self.led_manager.start_blinking()
            self.mqtt_handler.publish_ai_detection("DETECTED")
            blink_thread = threading.Thread(target=self.handle_blinking, daemon=True)
            blink_thread.start()
        else:
            logger.info("AI detected no obstacle.")
            self.mqtt_handler.publish_ai_detection("CLEAR")

    def on_garage_command(self, command):
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

    def update_system_enabled_state(self):
        previous_state = self.system_enabled
        self.system_enabled = self.user_is_home and self.garage_door_open
        logger.info(f"update_system_enabled_state: user_is_home={self.user_is_home}, garage_door_open={self.garage_door_open}, system_enabled={self.system_enabled}")
        if self.system_enabled != previous_state:
            logger.info(f"System enabled state changed to: {self.system_enabled}")
            self.mqtt_handler.publish_system_enabled(self.system_enabled)

    def on_user_status_update(self, status):
        self.user_is_home = (status.lower() == 'on')
        logger.info(f"Received user status update: {status}. User is home: {self.user_is_home}")
        self.update_system_enabled_state()

    def on_garage_state_update(self, state):
        logger.info(f"Received garage door state update: {state}")
        self.garage_door_open = (state.lower() == 'open')
        logger.info(f"Garage door is open: {self.garage_door_open}")
        self.update_system_enabled_state()

    def is_car_in_garage(self):
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

    def start_parking_procedure(self):
        with self.ai_lock:
            if not self.parking_procedure_active:
                logger.info("Garage door is open. Starting parking procedure.")
                self.measure_and_update_distances()

                # Allow time for LEDs to turn on and stabilize
                time.sleep(1)

                car_in_garage = self.is_car_in_garage()

                if car_in_garage:
                    self.process = "exiting"
                    logger.info("Process identified: Exiting the garage.")
                    self.mqtt_handler.publish_process(self.process)
                else:
                    self.process = "parking"
                    logger.info("Process identified: Parking procedure.")
                    self.mqtt_handler.publish_process(self.process)
                    self.ai_module.start()

                self.parking_procedure_active = True
            else:
                logger.info("Parking procedure already active.")

    def stop_parking_procedure(self):
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

    def measure_and_update_distances(self):
        with self.distances_lock:
            self.sensor_manager.measure_distances(self.distances)
            self.led_manager.update_leds(self.distances)

    def handle_automatic_garage_closure(self):
        with self.distances_lock:
            front_distance = self.distances.get('front')
        red_threshold_front = self.sensor_manager.red_distance_threshold.get('front')

        logger.debug(f"handle_garage_closure: front_distance={front_distance}, red_threshold_front={red_threshold_front}")

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
                        self.process == "parking" and
                        not self.close_command_sent):
                        logger.debug(
                            f"Front sensor detected red distance ({front_distance} cm) "
                            f"for {elapsed_time:.2f} seconds while in 'parking' state. Initiating garage door closure."
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

    def main_loop(self):
        if self.system_enabled:
            if self.led_manager.is_blinking():
                logger.debug("Blinking active. Skipping sensor measurements and MQTT updates.")
                self.led_manager.update_leds(self.distances)
            else:
                self.measure_and_update_distances()
                self.mqtt_handler.publish_distances(self.distances)
                self.handle_automatic_garage_closure()

            time.sleep(0.5)
        else:
            self.stop_parking_procedure()
            self.led_manager.clear_leds()
            logger.info("System disabled.")
            time.sleep(5)

    def start_flask_app(self):
        flask_thread = threading.Thread(target=run_flask_app, daemon=True)
        flask_thread.start()
        logger.info("Flask app started in a separate thread.")

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
        except Exception:
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
