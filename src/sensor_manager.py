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
        for sensor in ['front', 'left', 'right']:
            self.red_distance_threshold[sensor] = data.get(f"red_distance_threshold_{sensor}", self.red_distance_threshold[sensor])
            self.orange_distance_threshold[sensor] = data.get(f"orange_distance_threshold_{sensor}", self.orange_distance_threshold[sensor])

    def setup_sensors(self):
        setup_sensors(self.sensors)

    def measure_front_sensor(self, distances):
        sensor = self.sensors['front']
        distance = sensor.measure_distance()
        with distances['lock']:
            distances['front'] = distance
        logger.debug(f"Front measured distance: {distance} cm")

    def measure_side_sensors(self, distances):
        for sensor_name in ['left', 'right']:
            sensor = self.sensors[sensor_name]
            distance = sensor.measure_distance()
            with distances['lock']:
                distances[sensor_name] = distance
            logger.debug(f"{sensor_name.capitalize()} measured distance: {distance} cm")
            time.sleep(0.05)  # Short delay to prevent sensor interference

    def cleanup(self):
        cleanup()
