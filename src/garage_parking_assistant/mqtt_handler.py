# src/garage_parking_assistant/mqtt_handler.py

import paho.mqtt.client as mqtt
import logging
import time
from exceptions import MQTTError

logger = logging.getLogger(__name__)


class MqttHandler:
    """
    Handles MQTT connections, subscriptions, and message publishing.
    Implements observer pattern for message handling.
    """

    def __init__(self, config):
        self.client_id = "GarageParkingAssistantClient"
        self.client = mqtt.Client(client_id=self.client_id)
        self.config = config
        self.observers = []

    def register_observer(self, observer):
        """Register an observer to receive MQTT messages."""
        self.observers.append(observer)

    def notify_observers(self, topic, payload):
        """Notify all observers of a received MQTT message."""
        for observer in self.observers:
            observer.update(topic, payload)

    def connect(self):
        """
        Connect to the MQTT broker and subscribe to topics.
        Includes retry logic for connection.
        """
        attempts = 0
        max_attempts = 5
        while attempts < max_attempts:
            try:
                self.client.on_message = self.on_message
                self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
                self.client.subscribe([
                    (self.config.MQTT_TOPICS["settings"], 0),
                    (self.config.MQTT_TOPICS["garage_command"], 0),
                    (self.config.MQTT_TOPICS["user_status"], 0)
                ])
                self.client.loop_start()
                logger.info("Connected to MQTT broker and subscribed to topics.")
                return
            except Exception as e:
                attempts += 1
                logger.warning(f"MQTT connection attempt {attempts} failed: {e}")
                time.sleep(2)

        logger.error("Failed to connect to MQTT broker after multiple attempts.")
        raise MQTTError("MQTT connection failed.")

    def on_message(self, client, userdata, msg):
        """Callback for received MQTT messages."""
        try:
            payload = msg.payload.decode()
            logger.info(f"MQTT message received on {msg.topic}: {payload}")
            self.notify_observers(msg.topic, payload)
        except Exception as e:
            logger.exception(f"Failed to process MQTT message on {msg.topic}")

    def publish_distances(self, distances):
        """Publish sensor distances and availability."""
        for sensor in ['front', 'left', 'right']:
            distance = distances.get(sensor)
            distance_topic = f"{self.config.MQTT_BASE_TOPIC}/sensor/{sensor}/distance"
            availability_topic = f"{self.config.MQTT_BASE_TOPIC}/sensor/{sensor}/availability"
            if distance is not None:
                self.client.publish(distance_topic, str(distance))
                self.client.publish(availability_topic, "online")
            else:
                self.client.publish(availability_topic, "offline")

    def publish_garage_state(self, is_open):
        """Publish garage door state."""
        state = "open" if is_open else "closed"
        self.client.publish(self.config.MQTT_TOPICS["garage_state"], state, retain=True)
        logger.info(f"Published garage state: {state}")

    def publish_ai_detection(self, ai_detection):
        """Publish obstacle detection state."""
        self.client.publish(self.config.MQTT_TOPICS["ai_detection"], ai_detection, retain=True)
        logger.info(f"Published obstacle detection: {ai_detection}")

    def publish_process(self, process):
        """Publish current process state."""
        state = process if process else "IDLE"
        self.client.publish(self.config.MQTT_TOPICS["process_state"], state, retain=True)
        logger.info(f"Published process state: {state}")

    def publish_system_enabled(self, is_enabled):
        """Publish system enabled state."""
        state = "ON" if is_enabled else "OFF"
        self.client.publish(self.config.MQTT_TOPICS["system_enabled"], state, retain=True)
        logger.info(f"Published system enabled: {state}")

    def send_garage_command(self, command):
        """
        Send a command to the garage door ('OPEN' or 'CLOSE').
        """
        command = command.upper()
        if command in ["OPEN", "CLOSE"]:
            try:
                self.client.publish(self.config.MQTT_TOPICS["garage_command"], command)
                logger.info(f"Sent garage command: {command}")
            except Exception as e:
                logger.exception(f"Failed to send garage command: {command}")
                raise MQTTError(f"Failed to send command: {command}") from e
        else:
            logger.error(f"Invalid garage command: {command}")
            raise MQTTError(f"Invalid command: {command}")

    def publish_unauthorized_access_attempt(self):
        """Notify about unauthorized garage door access attempts."""
        topic = "garage/parking/unauthorized_access"
        payload = "Attempt to open garage door denied. User is not home."
        try:
            self.client.publish(topic, payload)
            logger.warning(f"Published unauthorized access attempt: {payload}")
        except Exception as e:
            logger.exception("Failed to publish unauthorized access attempt.")
            raise MQTTError("Unauthorized access publish failed.") from e

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker.")
        except Exception as e:
            logger.exception("Failed to disconnect from MQTT broker.")
            raise MQTTError("MQTT disconnection failed.") from e
