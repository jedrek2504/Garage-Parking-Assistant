# config.py

class Config:
    RED_DISTANCE_THRESHOLD = {
        'front': 10,
        'left': 10,
        'right': 10
    }
    ORANGE_DISTANCE_THRESHOLD = {
        'front': 20,
        'left': 20,
        'right': 20
    }
    BRIGHTNESS = 20
    SYSTEM_ENABLED = True
    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883
    MQTT_BASE_TOPIC = "garage/parking"
    MQTT_TOPICS = {
        "settings": "garage/parking/settings",
        "led_set": "garage/parking/led/set",
        "distance": "garage/parking/distance",
        "settings_get": "garage/parking/settings/get"
    }
