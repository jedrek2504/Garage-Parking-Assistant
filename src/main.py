import time
import paho.mqtt.client as mqtt
from sensor import setup_sensor, measure_distance
from led import set_led_color, clear_leds
import json

# Variables to store default MQTT settings
red_distance_threshold = 10 
orange_distance_threshold = 20
brightness = 20
system_enabled = True

# MQTT setup to handle settings updates
def on_message(client, userdata, msg):
    global red_distance_threshold, orange_distance_threshold, brightness, system_enabled
    
    payload = msg.payload.decode()
    print(f"Received MQTT message on {msg.topic}: {payload}")  # Log received payload for debugging
    try:
        data = json.loads(payload)
        if msg.topic == "garage/parking/settings":
            # Update system settings from the incoming message
            red_distance_threshold = data.get("red_distance_threshold", red_distance_threshold)
            orange_distance_threshold = data.get("orange_distance_threshold", orange_distance_threshold)
            brightness = data.get("brightness", brightness)
            system_enabled = data.get("enabled", system_enabled)
        elif msg.topic == "garage/parking/led/set":
            if data.get("state") == "ON":
                color = data.get("color", {})
                r = color.get("r", 0)
                g = color.get("g", 0)
                b = color.get("b", 0)
                set_led_color(r, g, b, brightness)
            else:
                clear_leds()
    except json.JSONDecodeError:
        print("Invalid JSON payload received")

# MQTT Client setup
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883, 60)

# Subscribe to both LED control and settings topics
mqtt_client.subscribe("garage/parking/led/set")
mqtt_client.subscribe("garage/parking/settings")
mqtt_client.loop_start()

if __name__ == "__main__":
    try:
        # Setup the sensor
        setup_sensor()

        while True:
            if system_enabled:
                # Measure distance only when the system is enabled
                distance = measure_distance()
                print(f"Measured Distance: {distance} cm")

                # Decide LED color based on the measured distance
                if distance < red_distance_threshold:
                    set_led_color(255, 0, 0, brightness)  # Red for close proximity
                elif distance < orange_distance_threshold:
                    set_led_color(255, 165, 0, brightness)  # Orange for caution zone
                else:
                    set_led_color(0, 255, 0, brightness)  # Green for safe distance

                # Publish distance data to MQTT
                mqtt_client.publish("garage/parking/distance", distance)
            else:
                # If the system is off, turn off the LEDs and minimize processing
                clear_leds()
                time.sleep(5)  # Sleep longer to reduce resource usage

            time.sleep(1)  # Wait 1 second before the next measurement when enabled

    except KeyboardInterrupt:
        print("Measurement stopped by User")
    finally:
        # Cleanup GPIO and turn off the LEDs
        clear_leds()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
