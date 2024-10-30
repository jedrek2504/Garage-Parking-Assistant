# mqtt_handler.py

import paho.mqtt.client as mqtt
import json
import logging
import time


logger = logging.getLogger(__name__)

class MqttHandler:
    def __init__(self, config, on_settings_update, on_led_set):
        self.client = mqtt.Client()
        self.config = config
        self.on_settings_update = on_settings_update
        self.on_led_set = on_led_set
        self.settings_received = False

    def connect(self):
        self.client.on_message = self.on_message
        self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
        for topic in [self.config.MQTT_TOPICS["settings"], self.config.MQTT_TOPICS["led_set"]]:
            self.client.subscribe(topic)
        self.client.loop_start()
        logger.info("MQTT client connected and subscribed to topics.")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        logger.debug(f"Received MQTT message on {msg.topic}: {payload}")
        try:
            data = json.loads(payload)
            if msg.topic == self.config.MQTT_TOPICS["settings"]:
                self.on_settings_update(data)
                self.settings_received = True
                logger.info("Settings updated from MQTT message.")
            elif msg.topic == self.config.MQTT_TOPICS["led_set"]:
                self.on_led_set(data)
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload received.")

    def publish_distance(self, distance):
        self.client.publish(self.config.MQTT_TOPICS["distance"], distance)
        logger.debug("Published distance to MQTT.")

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
