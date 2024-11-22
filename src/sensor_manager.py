# src/sensor_manager.py

import time
import logging
from sensor import UltrasonicSensor, setup_sensors, cleanup

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

    def setup_sensors(self):
        setup_sensors(self.sensors)

    def measure_distances(self, distances):
        # Measure all sensors
        for sensor_name in ['front', 'left', 'right']:
            sensor = self.sensors[sensor_name]
            distance = sensor.measure_distance()
            with distances['lock']:
                distances[sensor_name] = distance
            logger.debug(f"{sensor_name.capitalize()} measured distance: {distance} cm")
            time.sleep(0.05)  # Short delay to prevent sensor interference

    def cleanup(self):
        cleanup()
