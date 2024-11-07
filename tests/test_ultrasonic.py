import RPi.GPIO as GPIO
import time

# Set the GPIO mode
GPIO.setmode(GPIO.BCM)

# Define GPIO pins for each sensor based on your new assignments
SENSORS = {
    'front': {'trig': 22, 'echo': 23},  # GPIO22 and GPIO23
    'left': {'trig': 24, 'echo': 25},   # GPIO24 and GPIO25
    'right': {'trig': 17, 'echo': 27}   # GPIO17 and GPIO27
}

# Set up the GPIO pins for all sensors
for sensor in SENSORS.values():
    GPIO.setup(sensor['trig'], GPIO.OUT)
    GPIO.setup(sensor['echo'], GPIO.IN)

def measure_distance(trig_pin, echo_pin, sensor_name):
    # Ensure trigger pin is low
    GPIO.output(trig_pin, False)
    time.sleep(0.1)  # Short delay to settle sensor

    # Send a 10µs pulse to trigger
    GPIO.output(trig_pin, True)
    time.sleep(0.00001)
    GPIO.output(trig_pin, False)

    # Initialize start and stop times
    pulse_start = time.time()
    pulse_end = time.time()

    # Wait for the echo pin to go high
    timeout_start = time.time()
    while GPIO.input(echo_pin) == 0:
        pulse_start = time.time()
        if pulse_start - timeout_start > 1:
            print(f"{sensor_name.capitalize()} Sensor: Timeout waiting for echo start")
            return None

    # Wait for the echo pin to go low
    timeout_end = time.time()
    while GPIO.input(echo_pin) == 1:
        pulse_end = time.time()
        if pulse_end - timeout_end > 1:
            print(f"{sensor_name.capitalize()} Sensor: Timeout waiting for echo end")
            return None

    # Calculate pulse duration
    pulse_duration = pulse_end - pulse_start

    # Calculate distance (Speed of sound is 34300 cm/s)
    distance = pulse_duration * 17150  # 34300 / 2

    distance = round(distance, 2)

    return distance

try:
    while True:
        distances = {}
        for name, pins in SENSORS.items():
            distance = measure_distance(pins['trig'], pins['echo'], name)
            distances[name] = distance if distance is not None else "Error"
            time.sleep(0.1)  # Short delay to prevent sensor interference

        # Print the measured distances
        front_distance_str = f"{distances['front']} cm" if distances['front'] != "Error" else "Error"
        left_distance_str = f"{distances['left']} cm" if distances['left'] != "Error" else "Error"
        right_distance_str = f"{distances['right']} cm" if distances['right'] != "Error" else "Error"

        print(f"Front Sensor Distance: {front_distance_str} | Left Sensor Distance: {left_distance_str} | Right Sensor Distance: {right_distance_str}")

        # Wait before next measurement
        time.sleep(1)

except KeyboardInterrupt:
    print("Measurement stopped by User")
finally:
    GPIO.cleanup()

