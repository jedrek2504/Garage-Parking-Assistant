# src/garage_parking_assistant/sensors/ultrasonic_sensor.py

import time
import RPi.GPIO as GPIO
import logging
from exceptions import SensorError

logger = logging.getLogger(__name__)

class UltrasonicSensor:
    """
    Represents an ultrasonic distance sensor.
    Handles setup and distance measurement.
    """
    def __init__(self, trig_pin, echo_pin, name='Sensor'):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.name = name
        self.setup_sensor()

    def setup_sensor(self):
        """Initialize GPIO pins for the sensor."""
        try:
            GPIO.setup(self.trig_pin, GPIO.OUT)
            GPIO.setup(self.echo_pin, GPIO.IN)
            GPIO.output(self.trig_pin, False)
            time.sleep(2)  # Sensor stabilization
            logger.info(f"{self.name} initialized.")
        except Exception as e:
            logger.exception(f"{self.name}: Sensor setup failed.")
            raise SensorError(f"{self.name}: Setup failed.") from e

    def measure_distance(self):
        """
        Trigger the sensor and measure the distance.
        Returns distance in centimeters.
        """
        try:
            GPIO.output(self.trig_pin, True)
            time.sleep(0.00001)
            GPIO.output(self.trig_pin, False)

            pulse_start = time.time()
            pulse_end = time.time()

            # Wait for echo start
            timeout = time.time() + 0.05  # 50ms timeout
            while GPIO.input(self.echo_pin) == 0:
                pulse_start = time.time()
                if pulse_start > timeout:
                    logger.warning(f"{self.name}: Echo start timeout.")
                    raise SensorError(f"{self.name}: Echo start timeout.")

            # Wait for echo end
            timeout = time.time() + 0.05
            while GPIO.input(self.echo_pin) == 1:
                pulse_end = time.time()
                if pulse_end > timeout:
                    logger.warning(f"{self.name}: Echo end timeout.")
                    raise SensorError(f"{self.name}: Echo end timeout.")

            pulse_duration = pulse_end - pulse_start

            if pulse_duration <= 0 or pulse_duration > 0.04:  # 40ms max
                logger.warning(f"{self.name}: Invalid pulse duration: {pulse_duration}")
                raise SensorError(f"{self.name}: Invalid pulse duration.")

            distance = pulse_duration * 17150  # Convert to cm
            logger.debug(f"{self.name}: Distance measured: {distance:.2f} cm")
            return round(distance, 2)
        except SensorError as e:
            logger.error(f"{self.name}: {e}")
            raise
        except Exception as e:
            logger.exception(f"{self.name}: Distance measurement failed.")
            raise SensorError(f"{self.name}: Measurement failed.") from e
