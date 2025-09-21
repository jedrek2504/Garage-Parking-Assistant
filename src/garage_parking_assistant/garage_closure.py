# src/garage_parking_assistant/garage_closure.py

import time
import logging

logger = logging.getLogger(__name__)

class GarageClosureHandler:
    """
    Handles automatic garage closure based on proximity and timing.
    """

    def __init__(self):
        self.red_proximity_start_time = None

    def handle_automatic_garage_closure(self, front_distance, red_threshold, process, close_command_sent, system_enabled, send_garage_command, publish_system_enabled):
        """
        Automatically close garage door if car is within red proximity for 5 seconds.
        Returns updated close_command_sent and system_enabled.
        """
        if front_distance is not None and red_threshold is not None:
            if front_distance <= red_threshold:
                if not self.red_proximity_start_time:
                    self.red_proximity_start_time = time.time()
                    logger.debug("Car entered red proximity. Starting timer.")
                elif time.time() - self.red_proximity_start_time >= 5:
                    if process == "PARKING" and not close_command_sent:
                        logger.info("Closing garage door automatically due to prolonged proximity.")
                        send_garage_command("CLOSE")
                        close_command_sent = True
                        system_enabled = False
                        publish_system_enabled(system_enabled)
            else:
                if self.red_proximity_start_time:
                    logger.debug("Car exited red proximity. Resetting timer.")
                self.red_proximity_start_time = None
        else:
            self.red_proximity_start_time = None

        return close_command_sent, system_enabled
