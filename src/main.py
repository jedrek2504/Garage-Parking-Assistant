from sensor import setup_sensor, measure_distance, cleanup
from led import set_led_based_on_distance, clear_leds
import time

if __name__ == "__main__":
    try:
        # Setup the sensor
        setup_sensor()
        
        while True:
            # Measure distance
            distance = measure_distance()
            print(f"Measured Distance: {distance} cm")

            # Update LED strip based on the measured distance
            set_led_based_on_distance(distance)

            time.sleep(1)  # Wait 1 second before the next measurement

    except KeyboardInterrupt:
        print("Measurement stopped by User")
    finally:
        # Cleanup GPIO and turn off the LEDs
        clear_leds()
        cleanup()