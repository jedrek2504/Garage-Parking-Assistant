# src/garage_parking_assistant/config.py

import os

class Config:
    RED_DISTANCE_THRESHOLD = {
        'front': 3,
        'left': 3,
        'right': 3
    }
    ORANGE_DISTANCE_THRESHOLD = {
        'front': 10,
        'left': 10,
        'right': 10
    }
    BRIGHTNESS = 20
    SYSTEM_ENABLED = True
    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
    MQTT_BASE_TOPIC = "garage/parking"
    MQTT_TOPICS = {
        "settings": "garage/parking/settings",
        "garage_command": "garage/parking/garage_door/command",
        "garage_state": "garage/parking/garage_door/state",
        "ai_detection": "garage/parking/ai_detection",
        "process_state": "garage/parking/process_state",
        "user_status": "homeassistant/status/user_is_home",
        "system_enabled": "garage/parking/system_enabled",
    }
    BACKGROUND_FRAME_PATH = "background_frame.jpg"
