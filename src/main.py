from sensor import setup_sensor, measure_distance, cleanup
import time

if __name__ == "__main__":
    try:
        # Setup the sensor
        setup_sensor()

        while True:
            # Measure and display the distance
            dist = measure_distance()
            print(f"Measured Distance: {dist} cm")
            time.sleep(1)  # Wait 1 second before the next measurement

    except KeyboardInterrupt:
        print("Measurement stopped by User")
    finally:
        # Cleanup GPIO settings before exiting
        cleanup()
