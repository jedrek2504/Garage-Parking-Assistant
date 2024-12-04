# src/garage_parking_assistant/mqtt_handler.py

import paho.mqtt.client as mqtt
import logging

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

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        logger.info(f"Received MQTT message on {msg.topic}: {payload}")
        self.notify_observers(msg.topic, payload)

    def publish_distances(self, distances):
        for sensor_name in ['front', 'left', 'right']:
            distance = distances.get(sensor_name)
            distance_topic = f"{self.config.MQTT_BASE_TOPIC}/sensor/{sensor_name}/distance"
            availability_topic = f"{self.config.MQTT_BASE_TOPIC}/sensor/{sensor_name}/availability"
            
            if distance is not None:
                payload = str(distance)
                self.client.publish(distance_topic, payload)
                self.client.publish(availability_topic, "online")
            else:
                # When distance is None, mark sensor as offline
                self.client.publish(availability_topic, "offline")
                logger.debug(f"Published {sensor_name} availability: offline to topic {availability_topic}")

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
            self.client.publish(self.config.MQTT_TOPICS["garage_command"], command)
            logger.info(f"Sent garage command: {command} to topic {self.config.MQTT_TOPICS['garage_command']}")
        else:
            logger.error(f"Invalid garage command: {command}")

    def publish_unauthorized_access_attempt(self):
        """Publish a notification about an unauthorized attempt to open the garage door."""
        topic = "garage/parking/unauthorized_access"
        payload = "Attempt to open garage door denied. User is not home."
        self.client.publish(topic, payload, retain=False)
        logger.warning(f"Published unauthorized access attempt to topic {topic}: {payload}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT client disconnected.")
