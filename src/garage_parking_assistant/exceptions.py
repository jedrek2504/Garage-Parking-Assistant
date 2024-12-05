# src/garage_parking_assistant/exceptions.py

class GarageParkingAssistantError(Exception):
    """Base exception class for Garage-Parking-Assistant."""
    pass

class SensorError(GarageParkingAssistantError):
    """Exception raised for sensor-related errors."""
    def __init__(self, sensor_name, message="Sensor encountered an error"):
        self.sensor_name = sensor_name
        self.message = f"{message}: {sensor_name}"
        super().__init__(self.message)

class MQTTError(GarageParkingAssistantError):
    """Exception raised for MQTT-related errors."""
    def __init__(self, message="MQTT encountered an error"):
        self.message = message
        super().__init__(self.message)

class CameraError(GarageParkingAssistantError):
    """Exception raised for camera-related errors."""
    def __init__(self, message="Camera encountered an error"):
        self.message = message
        super().__init__(self.message)

class LEDManagerError(GarageParkingAssistantError):
    """Exception raised for LED manager-related errors."""
    def __init__(self, message="LED Manager encountered an error"):
        self.message = message
        super().__init__(self.message)
