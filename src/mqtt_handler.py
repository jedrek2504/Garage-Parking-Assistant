# mqtt_handler.py

import paho.mqtt.client as mqtt
import json
import logging
import time

logger = logging.getLogger(__name__)

class MqttHandler:
    def __init__(self, config, on_settings_update):
        self.client = mqtt.Client()
        self.config = config
        self.on_settings_update = on_settings_update
        self.settings_received = False

    def connect(self):
        self.client.on_message = self.on_message
        self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
        self.client.subscribe(self.config.MQTT_TOPICS["settings"])
        self.client.loop_start()
        logger.info("MQTT client connected and subscribed to settings topic.")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        logger.debug(f"Received MQTT message on {msg.topic}: {payload}")
        try:
            data = json.loads(payload)
            if msg.topic == self.config.MQTT_TOPICS["settings"]:
                self.on_settings_update(data)
                self.settings_received = True
                logger.info("Settings updated from MQTT message.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload received.")

    def publish_distances(self, distances):
        with distances['lock']:
            for sensor_name in ['front', 'left', 'right']:
                distance = distances.get(sensor_name)
                if distance is not None:
                    topic = f"{self.config.MQTT_BASE_TOPIC}/sensor/{sensor_name}/distance"
                    self.client.publish(topic, str(distance))
                    logger.debug(f"Published {sensor_name} distance: {distance} cm")

    def request_settings(self):
        logger.info("Requesting current settings from Home Assistant...")
        self.client.publish(self.config.MQTT_TOPICS["settings_get"], "")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT client disconnected.")

    def wait_for_settings(self):
        while not self.settings_received:
            logger.debug("Waiting for settings...")
            time.sleep(1)
