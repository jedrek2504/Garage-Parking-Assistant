import RPi.GPIO as GPIO
import time

# Define the GPIO pins for the sensor
ECHO = 23
TRIG = 24


def setup_sensor():
    """Initializes the GPIO pins for the ultrasonic sensor."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.output(TRIG, False)
    print("Waiting for sensor to settle")
    time.sleep(2)  # Allow sensor to settle

def measure_distance():
    """Measures the distance using the HC-SR04 sensor."""
    # Triggering the sensor
    GPIO.output(TRIG, True)
    time.sleep(0.00001)  # Trigger pulse for 10µs
    GPIO.output(TRIG, False)

    # Measure the duration of the echo signal
    pulse_start = time.time()
    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()

    pulse_end = time.time()
    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()

    # Calculate the time difference
    pulse_duration = pulse_end - pulse_start
    # Calculate distance based on pulse duration
    distance = pulse_duration * 17150  # Distance in cm
    return round(distance, 2)

def cleanup():
    """Cleans up the GPIO pins."""
    GPIO.cleanup()
