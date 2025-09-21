import RPi.GPIO as GPIO
import time
from rpi_ws281x import PixelStrip, Color

# LED strip configuration:
LED_COUNT = 37        # Number of LED pixels.
LED_PIN = 18          # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800kHz).
LED_DMA = 10          # DMA channel to use for generating signal (try 10).
LED_BRIGHTNESS = 20  # Set to 0 for darkest and 255 for brightest (capped at 100).
LED_INVERT = False    # True to invert the signal (when using NPN transistor level shift).
LED_CHANNEL = 0

# Set the GPIO mode
GPIO.setmode(GPIO.BCM)

# Define GPIO pins for each sensor
SENSORS = {
    'front': {'trig': 22, 'echo': 23},  # GPIO22 and GPIO23
    'left':  {'trig': 24, 'echo': 25},  # GPIO24 and GPIO25
    'right': {'trig': 17, 'echo': 27}   # GPIO17 and GPIO27
}

# Set up the GPIO pins for all sensors
for sensor in SENSORS.values():
    GPIO.setup(sensor['trig'], GPIO.OUT)
    GPIO.setup(sensor['echo'], GPIO.IN)

# Create NeoPixel object with appropriate configuration.
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

def measure_distance(trig_pin, echo_pin, sensor_name):
    # Ensure trigger pin is low
    GPIO.output(trig_pin, False)
    time.sleep(0.05)  # Short delay to settle sensor

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

def get_color_for_distance(distance):
    if distance is None:
        return Color(0, 0, 0)  # Off if no reading
    elif distance < 3:
        return Color(255, 0, 0)  # Red
    elif distance < 10:
        return Color(255, 165, 0)  # Orange
    else:
        return Color(0, 255, 0)  # Green

def set_led_segment_color(start_index, end_index, color):
    for i in range(start_index, end_index):
        strip.setPixelColor(i, color)
    strip.show()

try:
    while True:
        distances = {}
        for name, pins in SENSORS.items():
            distance = measure_distance(pins['trig'], pins['echo'], name)
            distances[name] = distance
            time.sleep(0.05)  # Short delay to prevent sensor interference

        # Map sensors to LED segments
        # Left Sensor controls LEDs 0-9
        # Front Sensor controls LEDs 10-19
        # Right Sensor controls LEDs 20-29
        sensor_to_led = {
            'left': {'start': 0, 'end': 11},    # LEDs 0-11
            'front': {'start': 14, 'end': 22},  # LEDs 14-22
            'right': {'start': 25, 'end': 37}   # LEDs 25-37
        }

        for sensor_name, distance in distances.items():
            color = get_color_for_distance(distance)
            start = sensor_to_led[sensor_name]['start']
            end = sensor_to_led[sensor_name]['end']
            set_led_segment_color(start, end, color)

        # Print the measured distances
        front_distance_str = f"{distances['front']} cm" if distances['front'] is not None else "Error"
        left_distance_str = f"{distances['left']} cm" if distances['left'] is not None else "Error"
        right_distance_str = f"{distances['right']} cm" if distances['right'] is not None else "Error"

        print(f"Front Sensor Distance: {front_distance_str} | Left Sensor Distance: {left_distance_str} | Right Sensor Distance: {right_distance_str}")

        # Wait before next measurement
        time.sleep(5)

except KeyboardInterrupt:
    print("Measurement stopped by User")
    # Turn off all LEDs before exiting
    for i in range(LED_COUNT):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
finally:
    GPIO.cleanup()

