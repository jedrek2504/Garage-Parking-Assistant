# src/garage_parking_assistant/sensors/ultrasonic_sensor.py

import time
import RPi.GPIO as GPIO
import logging
from exceptions import SensorError

logger = logging.getLogger(__name__)

class UltrasonicSensor:
    def __init__(self, trig_pin, echo_pin, name='Sensor'):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.name = name
        self.setup_sensor()

    def setup_sensor(self):
        try:
            GPIO.setup(self.trig_pin, GPIO.OUT)
            GPIO.setup(self.echo_pin, GPIO.IN)
            GPIO.output(self.trig_pin, False)
            time.sleep(2)
            logger.info(f"{self.name} setup complete.")
        except Exception as e:
            logger.exception(f"{self.name}: Failed to setup sensor.")
            raise SensorError(f"{self.name}: Failed to setup sensor.") from e

    def measure_distance(self):
        try:
            GPIO.output(self.trig_pin, True)
            time.sleep(0.00001)
            GPIO.output(self.trig_pin, False)

            pulse_start = time.time()
            pulse_end = time.time()

            # Wait for the pulse to start
            timeout_start = time.time()
            while GPIO.input(self.echo_pin) == 0:
                pulse_start = time.time()
                if pulse_start - timeout_start > 0.05:
                    logger.warning(f"{self.name}: Timeout waiting for pulse to start.")
                    raise SensorError(f"{self.name}: Timeout waiting for pulse to start.")

            # Wait for the pulse to end
            timeout_end = time.time()
            while GPIO.input(self.echo_pin) == 1:
                pulse_end = time.time()
                if pulse_end - timeout_end > 0.05:
                    logger.warning(f"{self.name}: Timeout waiting for pulse to end.")
                    raise SensorError(f"{self.name}: Timeout waiting for pulse to end.")

            pulse_duration = pulse_end - pulse_start

            # Validate pulse_duration
            if pulse_duration <= 0 or pulse_duration > 0.04:  # Max 40 ms
                logger.warning(f"{self.name}: Invalid pulse duration: {pulse_duration}")
                raise SensorError(f"{self.name}: Invalid pulse duration")

            distance = pulse_duration * 17150
            logger.debug(f"{self.name}: Measured distance: {distance:.2f} cm")
            return round(distance, 2)
        except SensorError as e:
            logger.error(f"{self.name}: {e}")
            raise
        except Exception as e:
            logger.exception(f"{self.name}: Failed to measure distance.")
            raise SensorError(f"{self.name}: Failed to measure distance.") from e
