# src/sensor.py

import time
import RPi.GPIO as GPIO
import logging

logger = logging.getLogger(__name__)

class UltrasonicSensor:
    def __init__(self, trig_pin, echo_pin, name='Sensor'):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.name = name
        self.setup_sensor()

    def setup_sensor(self):
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        GPIO.output(self.trig_pin, False)
        time.sleep(2)
        logger.info(f"{self.name} setup complete.")

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
                    return None

            # Wait for the pulse to end
            timeout_end = time.time()
            while GPIO.input(self.echo_pin) == 1:
                pulse_end = time.time()
                if pulse_end - timeout_end > 0.05:
                    logger.warning(f"{self.name}: Timeout waiting for pulse to end.")
                    return None

            pulse_duration = pulse_end - pulse_start
            distance = pulse_duration * 17150
            logger.debug(f"{self.name}: Measured distance: {distance:.2f} cm")
            return round(distance, 2)
        except Exception as e:
            logger.exception(f"{self.name}: Failed to measure distance.")
            return None

def setup_sensors(sensors):
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for sensor in sensors.values():
            sensor.setup_sensor()
        logger.info("All sensors setup complete.")
    except Exception as e:
        logger.exception("Failed to setup sensors.")

def cleanup():
    GPIO.cleanup()
    logger.info("GPIO cleanup complete.")
