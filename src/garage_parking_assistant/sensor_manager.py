# src/garage_parking_assistant/sensor_manager.py

import time
import logging
import RPi.GPIO as GPIO
from sensors.ultrasonic_sensor import UltrasonicSensor
from exceptions import SensorError, GarageParkingAssistantError

logger = logging.getLogger(__name__)

class SensorManager:
    """
    Manages ultrasonic sensors for front, left, and right.
    Handles setup, measurement, and cleanup.
    """
    def __init__(self, config):
        self.config = config
        self.sensors = {
            'front': UltrasonicSensor(trig_pin=22, echo_pin=23, name='Front Sensor'),
            'left': UltrasonicSensor(trig_pin=24, echo_pin=25, name='Left Sensor'),
            'right': UltrasonicSensor(trig_pin=17, echo_pin=27, name='Right Sensor')
        }
        self.red_distance_threshold = self.config.RED_DISTANCE_THRESHOLD.copy()
        self.orange_distance_threshold = self.config.ORANGE_DISTANCE_THRESHOLD.copy()

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
        Measure distances from all sensors and update the distances dict.
        """
        for sensor_name, sensor in self.sensors.items():
            try:
                distance = sensor.measure_distance()
                distances[sensor_name] = distance
                logger.debug(f"{sensor_name.capitalize()} distance: {distance} cm")
            except SensorError as e:
                logger.error(f"{sensor_name.capitalize()} measurement error: {e}")
                distances[sensor_name] = None
            except Exception as e:
                logger.exception(f"Unexpected error measuring {sensor_name}.")
                distances[sensor_name] = None
            time.sleep(0.05)  # Prevent sensor interference

    def cleanup(self):
        """Clean up GPIO settings."""
        try:
            GPIO.cleanup()
            logger.info("GPIO cleanup completed.")
        except Exception as e:
            logger.exception("GPIO cleanup failed.")
            raise GarageParkingAssistantError("GPIO cleanup failed.") from e
