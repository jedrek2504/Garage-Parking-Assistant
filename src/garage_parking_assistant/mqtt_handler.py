# src/garage_parking_assistant/mqtt_handler.py

import paho.mqtt.client as mqtt
import logging
from exceptions import MQTTError

logger = logging.getLogger(__name__)

class MqttHandler:
    def __init__(self, config):
        self.client = mqtt.Client()
        self.config = config
        self.observers = []

    def register_observer(self, observer):
        self.observers.append(observer)

    def notify_observers(self, topic, payload):
        for observer in self.observers:
            observer.update(topic, payload)

    def connect(self):
        try:
            self.client.on_message = self.on_message
            self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
            self.client.subscribe([
                (self.config.MQTT_TOPICS["settings"], 0),
                (self.config.MQTT_TOPICS["garage_command"], 0),
                (self.config.MQTT_TOPICS["user_status"], 0),
                (self.config.MQTT_TOPICS["garage_state"], 0)
            ])
            self.client.loop_start()
            logger.info("MQTT client connected and subscribed to topics.")
        except Exception as e:
            logger.exception("Failed to connect MQTT client.")
            raise MQTTError("Failed to connect MQTT client") from e

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            logger.info(f"Received MQTT message on {msg.topic}: {payload}")
            self.notify_observers(msg.topic, payload)
        except Exception as e:
            logger.exception(f"Failed to process incoming MQTT message on {msg.topic}")
            # Depending on the criticality, you might want to raise or handle differently

    def publish_distances(self, distances):
        for sensor_name in ['front', 'left', 'right']:
            distance = distances.get(sensor_name)
            distance_topic = f"{self.config.MQTT_BASE_TOPIC}/sensor/{sensor_name}/distance"
            availability_topic = f"{self.config.MQTT_BASE_TOPIC}/sensor/{sensor_name}/availability"
            
            if distance is not None:
                payload = str(distance)
                self.client.publish(distance_topic, payload)
                self.client.publish(availability_topic, "online")
                # Keep it commented unless needed -> too much junk.
                # logger.debug(f"Published distance for {sensor_name}: {distance} cm to topic {distance_topic}")
            else:
                # When distance is None, mark sensor as offline
                self.client.publish(availability_topic, "offline")
                # Keep it commented unless needed -> too much junk.
                # logger.debug(f"Sensor '{sensor_name}' is offline. Published to topic {availability_topic}")

    def publish_garage_state(self, is_open):
        state = "open" if is_open else "closed"
        self.client.publish(self.config.MQTT_TOPICS["garage_state"], state, retain=True)
        logger.info(f"Published garage door state: {state} to topic {self.config.MQTT_TOPICS['garage_state']}")

    def publish_ai_detection(self, ai_detection):
        topic = self.config.MQTT_TOPICS["ai_detection"]
        self.client.publish(topic, ai_detection, retain=True)
        logger.info(f"Published AI detection state: {ai_detection} to topic {topic}")

    def publish_process(self, process):
        topic = self.config.MQTT_TOPICS["process_state"]
        payload = process
        self.client.publish(topic, payload, retain=True)
        logger.info(f"Published process state: {payload} to topic {topic}")

    def publish_system_enabled(self, is_enabled):
        state = "ON" if is_enabled else "OFF"
        topic = self.config.MQTT_TOPICS["system_enabled"]
        self.client.publish(topic, state, retain=True)
        logger.info(f"Published system enabled state: {state} to topic {topic}")

    def send_garage_command(self, command):
        """Send a command to the garage door ('OPEN' or 'CLOSE')."""
        command = command.upper()
        if command in ["OPEN", "CLOSE"]:
            try:
                self.client.publish(self.config.MQTT_TOPICS["garage_command"], command)
                logger.info(f"Sent garage command: {command} to topic {self.config.MQTT_TOPICS['garage_command']}")
            except Exception as e:
                logger.exception(f"Failed to send garage command: {command}")
                raise MQTTError(f"Failed to send garage command: {command}") from e
        else:
            logger.error(f"Invalid garage command: {command}")
            raise MQTTError(f"Invalid garage command: {command}")

    def publish_unauthorized_access_attempt(self):
        """Publish a notification about an unauthorized attempt to open the garage door."""
        topic = "garage/parking/unauthorized_access"
        payload = "Attempt to open garage door denied. User is not home."
        try:
            self.client.publish(topic, payload, retain=False)
            logger.warning(f"Published unauthorized access attempt to topic {topic}: {payload}")
        except Exception as e:
            logger.exception("Failed to publish unauthorized access attempt.")
            raise MQTTError("Failed to publish unauthorized access attempt.") from e

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected.")
        except Exception as e:
            logger.exception("Failed to disconnect MQTT client.")
            raise MQTTError("Failed to disconnect MQTT client") from e
