import time
import paho.mqtt.client as mqtt
from sensor import setup_sensor, measure_distance
from led import set_led_color, clear_leds
import json

# MQTT setup
def on_message(client, userdata, msg):
    """Handle incoming MQTT messages for LED control."""
    payload = msg.payload.decode()
    try:
        data = json.loads(payload)
        if data.get("state") == "ON":
            brightness = data.get("brightness", 255)
            color = data.get("color", {})
            r = color.get("r", 0)
            g = color.get("g", 0)
            b = color.get("b", 0)
            set_led_color(r, g, b, brightness)
        else:
            clear_leds()
    except json.JSONDecodeError:
        print("Invalid JSON payload received")

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883, 60)
mqtt_client.subscribe("garage/parking/led/set")
mqtt_client.loop_start()

if __name__ == "__main__":
    try:
        # Setup the sensor
        setup_sensor()

        while True:
            # Measure distance
            distance = measure_distance()
            print(f"Measured Distance: {distance} cm")

            # Publish distance data to MQTT
            mqtt_client.publish("garage/parking/distance", distance)

            time.sleep(1)  # Wait 1 second before the next measurement

    except KeyboardInterrupt:
        print("Measurement stopped by User")
    finally:
        # Cleanup GPIO and turn off the LEDs
        clear_leds()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
