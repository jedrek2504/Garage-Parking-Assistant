# src/garage_parking_assistant/config.py
import os
import yaml
import logging

logger = logging.getLogger(__name__)

class Config:
    """
    Loads configuration from config.yaml if available, otherwise falls back to defaults.
    """

    def __init__(self):
        self._load_from_yaml()

    def _load_from_yaml(self):
        default_config = {
            'mqtt': {
                'broker': os.getenv("MQTT_BROKER", "localhost"),
                'port': int(os.getenv("MQTT_PORT", 1883)),
                'base_topic': "garage/parking",
                'topics': {
                    "settings": "garage/parking/settings",
                    "garage_command": "garage/parking/garage_door/command",
                    "garage_state": "garage/parking/garage_door/state",
                    "ai_detection": "garage/parking/ai_detection",
                    "process_state": "garage/parking/process_state",
                    "user_status": "homeassistant/status/user_is_home",
                    "system_enabled": "garage/parking/system_enabled"
                }
            },
            'sensors': {
                'front': {'type': 'ultrasonic', 'trig_pin': 22, 'echo_pin': 23},
                'left': {'type': 'ultrasonic', 'trig_pin': 24, 'echo_pin': 25},
                'right': {'type': 'ultrasonic', 'trig_pin': 17, 'echo_pin': 27}
            },
            'thresholds': {
                'red': {'front': 3, 'left': 3, 'right': 3},
                'orange': {'front': 10, 'left': 10, 'right': 10}
            },
            'led': {
                'brightness': 20
            },
            'system': {
                'enabled': False
            },
            'logging': {
                'level': 'INFO',
                'file': 'garage_parking_assistant.log'
            },
            'background_frame_path': 'background_frame.jpg'
        }

        if os.path.exists("config.yaml"):
            try:
                with open("config.yaml", "r") as f:
                    user_config = yaml.safe_load(f)
                # Merge user_config into default_config
                self._deep_update(default_config, user_config)
            except Exception as e:
                logger.warning("Failed to read or parse config.yaml, using defaults. Error: %s", e)

        cfg = default_config
        self.MQTT_BROKER = cfg['mqtt']['broker']
        self.MQTT_PORT = cfg['mqtt']['port']
        self.MQTT_BASE_TOPIC = cfg['mqtt']['base_topic']
        self.MQTT_TOPICS = cfg['mqtt']['topics']
        self.SENSORS_CONFIG = cfg['sensors']
        self.RED_DISTANCE_THRESHOLD = cfg['thresholds']['red']
        self.ORANGE_DISTANCE_THRESHOLD = cfg['thresholds']['orange']
        self.BRIGHTNESS = cfg['led']['brightness']
        self.SYSTEM_ENABLED = cfg['system']['enabled']
        self.BACKGROUND_FRAME_PATH = cfg['background_frame_path']

        log_level = cfg['logging'].get('level', 'INFO')
        log_file = cfg['logging'].get('file', 'garage_parking_assistant.log')
        logging.getLogger().setLevel(log_level.upper())
        # File handler might already be configured in main.py, ensure consistency
        for handler in logging.getLogger().handlers:
            if hasattr(handler, 'baseFilename'):
                # If file handler exists, update its filename if needed
                pass

    def _deep_update(self, source, overrides):
        for key, value in overrides.items():
            if isinstance(value, dict) and key in source:
                self._deep_update(source[key], value)
            else:
                source[key] = value
