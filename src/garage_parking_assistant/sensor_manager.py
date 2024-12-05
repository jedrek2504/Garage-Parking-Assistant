# src/garage_parking_assistant/sensor_manager.py

import time
import logging
import RPi.GPIO as GPIO
from sensors.ultrasonic_sensor import UltrasonicSensor
from exceptions import SensorError, GarageParkingAssistantError

logger = logging.getLogger(__name__)

class SensorManager:
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
            logger.exception("Failed to update thresholds.")
            raise GarageParkingAssistantError("Failed to update sensor thresholds") from e

    def setup_sensors(self):
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            for sensor in self.sensors.values():
                sensor.setup_sensor()
            logger.info("All sensors setup complete.")
        except Exception as e:
            logger.exception("Failed to setup sensors.")
            raise SensorError("SensorManager", "Failed to setup sensors") from e

    def measure_distances(self, distances):
        # Measure all sensors
        for sensor_name in ['front', 'left', 'right']:
            sensor = self.sensors[sensor_name]
            try:
                distance = sensor.measure_distance()
                distances[sensor_name] = distance
                logger.debug(f"{sensor_name.capitalize()} measured distance: {distance} cm")
            except SensorError as e:
                logger.error(f"Error measuring distance for {sensor_name}: {e}")
                distances[sensor_name] = None
            except Exception as e:
                logger.exception(f"Unexpected error measuring distance for {sensor_name}.")
                distances[sensor_name] = None
            time.sleep(0.05)  # Short delay to prevent sensor interference

    def cleanup(self):
        try:
            GPIO.cleanup()
            logger.info("GPIO cleanup complete.")
        except Exception as e:
            logger.exception("Failed to cleanup GPIO.")
            raise GarageParkingAssistantError("Failed to cleanup GPIO") from e
