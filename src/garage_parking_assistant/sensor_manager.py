# src/garage_parking_assistant/sensor_manager.py

import time
import logging
import RPi.GPIO as GPIO
from exceptions import SensorError, GarageParkingAssistantError
from sensors.ultrasonic_sensor import UltrasonicSensor, BaseSensor

logger = logging.getLogger(__name__)

def sensor_factory(sensor_config):
    stype = sensor_config.get('type', 'ultrasonic')
    if stype == 'ultrasonic':
        return UltrasonicSensor(trig_pin=sensor_config['trig_pin'], echo_pin=sensor_config['echo_pin'])
    else:
        raise GarageParkingAssistantError(f"Unknown sensor type: {stype}")

class SensorManager:
    """
    Manages sensors and their measurements.
    Includes retry logic on sensor readings.
    """

    def __init__(self, config):
        self.config = config
        self.red_distance_threshold = self.config.RED_DISTANCE_THRESHOLD.copy()
        self.orange_distance_threshold = self.config.ORANGE_DISTANCE_THRESHOLD.copy()

        self.sensors = {}
        for name, scfg in self.config.SENSORS_CONFIG.items():
            self.sensors[name] = sensor_factory(scfg)

    def update_thresholds(self, data):
        """
        Update distance thresholds based on incoming data.
        """
        try:
            for color in ['red', 'orange']:
                for sensor in ['front', 'left', 'right']:
                    key = f"{color}_distance_threshold_{sensor}"
                    if key in data:
                        threshold = data[key]
                        if color == 'red':
                            self.red_distance_threshold[sensor] = threshold
                        else:
                            self.orange_distance_threshold[sensor] = threshold
                        logger.debug(f"Updated {color} threshold for {sensor} to {threshold}")
        except Exception as e:
            logger.exception("Failed to update sensor thresholds.")
            raise GarageParkingAssistantError("Sensor thresholds update failed.") from e

    def setup_sensors(self):
        """Initialize GPIO and set up all sensors."""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            for sensor in self.sensors.values():
                sensor.setup_sensor()
            logger.info("All sensors initialized.")
        except Exception as e:
            logger.exception("Sensor setup failed.")
            raise SensorError("SensorManager", "Sensor setup failed.") from e

    def measure_distances(self, distances):
        """
        Measure distances from all sensors with retry logic.
        """
        for sensor_name, sensor in self.sensors.items():
            success = False
            attempts = 0
            max_attempts = 3
            measured_distance = None

            while not success and attempts < max_attempts:
                try:
                    measured_distance = sensor.measure_distance()
                    success = True
                except SensorError as e:
                    attempts += 1
                    logger.warning(f"Attempt {attempts} failed measuring {sensor_name}: {e}")
                    time.sleep(0.1)

            if not success:
                logger.error(f"Failed to measure distance from {sensor_name} after {max_attempts} attempts.")
                distances[sensor_name] = None
            else:
                distances[sensor_name] = measured_distance
                logger.debug(f"{sensor_name.capitalize()} distance: {measured_distance} cm")

            time.sleep(0.05)  # Prevent sensor interference

    def cleanup(self):
        """Clean up GPIO settings."""
        try:
            GPIO.cleanup()
            logger.info("GPIO cleanup completed.")
        except Exception as e:
            logger.exception("GPIO cleanup failed.")
            raise GarageParkingAssistantError("GPIO cleanup failed.") from e
