# src/garage_parking_assistant/exceptions.py

class GarageParkingAssistantError(Exception):
    """Base exception for Garage-Parking-Assistant."""
    pass

class SensorError(GarageParkingAssistantError):
    """Exception for sensor-related issues."""
    def __init__(self, sensor_name, message="Sensor error"):
        self.sensor_name = sensor_name
        self.message = f"{message}: {sensor_name}"
        super().__init__(self.message)

class MQTTError(GarageParkingAssistantError):
    """Exception for MQTT-related issues."""
    def __init__(self, message="MQTT error"):
        self.message = message
        super().__init__(self.message)

class CameraError(GarageParkingAssistantError):
    """Exception for camera-related issues."""
    def __init__(self, module="CameraError", message="Camera error"):
        self.module = module
        self.message = message
        super().__init__(f"[{self.module}] {self.message}")


class LEDManagerError(GarageParkingAssistantError):
    """Exception for LED manager issues."""
    def __init__(self, message="LED Manager error"):
        self.message = message
        super().__init__(self.message)
