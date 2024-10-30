# sensor.py

import time
import RPi.GPIO as GPIO
import logging

logger = logging.getLogger(__name__)

# Define the GPIO pins for the sensor
ECHO = 23
TRIG = 24

def setup_sensor():
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(TRIG, GPIO.OUT)
        GPIO.setup(ECHO, GPIO.IN)
        GPIO.output(TRIG, False)
        time.sleep(2)
        logger.info("Sensor setup complete.")
    except Exception as e:
        logger.exception("Failed to setup sensor.")

def measure_distance():
    try:
        GPIO.output(TRIG, True)
        time.sleep(0.00001)
        GPIO.output(TRIG, False)

        pulse_start = time.time()
        pulse_end = time.time()

        # Wait for the pulse to start
        timeout_start = time.time()
        while GPIO.input(ECHO) == 0:
            pulse_start = time.time()
            if pulse_start - timeout_start > 0.05:
                logger.warning("Timeout waiting for pulse to start.")
                return None

        # Wait for the pulse to end
        timeout_end = time.time()
        while GPIO.input(ECHO) == 1:
            pulse_end = time.time()
            if pulse_end - timeout_end > 0.05:
                logger.warning("Timeout waiting for pulse to end.")
                return None

        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17150
        logger.debug(f"Measured distance: {distance:.2f} cm")
        return round(distance, 2)
    except Exception as e:
        logger.exception("Failed to measure distance.")
        return None

def cleanup():
    GPIO.cleanup()
    logger.info("GPIO cleanup complete.")
