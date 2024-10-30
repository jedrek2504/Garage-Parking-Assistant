# main.py

import time
import threading
import json
import paho.mqtt.client as mqtt
from sensor import setup_sensor, measure_distance
from led import set_led_color, clear_leds

# Import the run_flask_app function
from camera_stream import run_flask_app

import logging

# Configure logging for main.py and other components (excluding the Flask app)
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG to see debug messages
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('garage_parking_assistant.log')
    ]
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Variables to store default MQTT settings
red_distance_threshold = 10
orange_distance_threshold = 20
brightness = 20
system_enabled = True
settings_received = False  # Track whether settings have been received

# MQTT setup to handle settings updates
def on_message(client, userdata, msg):
    global red_distance_threshold, orange_distance_threshold, brightness, system_enabled, settings_received

    payload = msg.payload.decode()
    logger.debug(f"Received MQTT message on {msg.topic}: {payload}")
    try:
        data = json.loads(payload)
        if msg.topic == "garage/parking/settings":
            # Update system settings from the incoming message
            red_distance_threshold = data.get("red_distance_threshold", red_distance_threshold)
            orange_distance_threshold = data.get("orange_distance_threshold", orange_distance_threshold)
            brightness = data.get("brightness", brightness)
            system_enabled = data.get("enabled", system_enabled)
            settings_received = True  # Mark that settings have been received
            logger.info("Settings updated from MQTT message.")
        elif msg.topic == "garage/parking/led/set":
            if data.get("state") == "ON":
                color = data.get("color", {})
                r = color.get("r", 0)
                g = color.get("g", 0)
                b = color.get("b", 0)
                set_led_color(r, g, b, brightness)
                logger.info(f"LED color set to RGB({r}, {g}, {b}) with brightness {brightness}.")
            else:
                clear_leds()
                logger.info("LEDs cleared.")
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload received.")

# MQTT Client setup
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883, 60)

# Subscribe to both LED control and settings topics
mqtt_client.subscribe("garage/parking/led/set")
mqtt_client.subscribe("garage/parking/settings")
mqtt_client.loop_start()
logger.info("MQTT client connected and subscribed to topics.")

# Function to request the current settings on startup
def request_current_settings():
    logger.info("Requesting current settings from Home Assistant...")
    mqtt_client.publish("garage/parking/settings/get", "")

if __name__ == "__main__":
    try:
        # Setup the sensor
        setup_sensor()
        logger.info("Sensor setup complete.")

        # Request current settings from Home Assistant
        request_current_settings()

        # Start the Flask app in a separate thread
        flask_thread = threading.Thread(target=run_flask_app)
        flask_thread.daemon = True  # Daemonize thread to exit when main thread exits
        flask_thread.start()
        logger.info("Flask app started in a separate thread.")

        # Wait until settings are received before proceeding
        while not settings_received:
            logger.debug("Waiting for settings...")
            time.sleep(1)  # Wait for 1 second before checking again

        logger.info("Settings received. Starting main loop.")

        # Main loop for measuring distance and controlling the LEDs
        while True:
            if system_enabled:
                # Measure distance only when the system is enabled
                distance = measure_distance()
                if distance is not None:
                    logger.debug(f"Measured Distance: {distance} cm")

                    # Decide LED color based on the measured distance
                    if distance < red_distance_threshold:
                        set_led_color(255, 0, 0, brightness)  # Red for close proximity
                        logger.debug("Set LED color to RED.")
                    elif distance < orange_distance_threshold:
                        set_led_color(255, 165, 0, brightness)  # Orange for caution zone
                        logger.debug("Set LED color to ORANGE.")
                    else:
                        set_led_color(0, 255, 0, brightness)  # Green for safe distance
                        logger.debug("Set LED color to GREEN.")

                    # Publish distance data to MQTT
                    mqtt_client.publish("garage/parking/distance", distance)
                    logger.debug("Published distance to MQTT.")
                else:
                    logger.error("Failed to measure distance.")
            else:
                # If the system is off, turn off the LEDs and minimize processing
                clear_leds()
                logger.info("System disabled. LEDs turned off.")
                time.sleep(5)  # Sleep longer to reduce resource usage

            time.sleep(1)  # Wait 1 second before the next measurement when enabled

    except KeyboardInterrupt:
        logger.info("Measurement stopped by User.")
    except Exception as e:
        logger.exception("An unexpected error occurred.")
    finally:
        # Cleanup GPIO and turn off the LEDs
        clear_leds()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client disconnected and resources cleaned up.")
        # The Flask app will exit because the thread is a daemon
